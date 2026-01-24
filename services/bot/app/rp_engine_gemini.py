import os
import json
import logging
import re
from typing import Optional, List, Dict
from google import genai
from google.genai import types

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Using the user's provided default (even though 2.5 isn't public, it's configurable)
DEFAULT_MODEL = os.getenv("GEMINI_RP_MODEL", "gemini-2.0-flash-lite")
TIMEOUT = int(os.getenv("GEMINI_RP_TIMEOUT_SECONDS", "10"))
MAX_TOKENS = int(os.getenv("GEMINI_RP_MAX_OUTPUT_TOKENS", "160"))
TEMPERATURE = float(os.getenv("GEMINI_RP_TEMPERATURE", "0.3"))

logger = logging.getLogger(__name__)

# Suffixing/Trimming Config
COMPUTER_PREFIX = os.getenv("COMPUTER_PREFIX", "Computer:")
STYLE_STRICT = os.getenv("RP_STYLE_STRICT", "true").lower() == "true"

_STYLE_CACHE: Dict[str, str] = {}

def _load_style_spec() -> str:
    """Loads Rules and Examples from docs/computer_style.md."""
    if "spec" in _STYLE_CACHE:
        return _STYLE_CACHE["spec"]
    
    spec_path = os.path.join(os.path.dirname(__file__), "../../../docs/computer_style.md")
    if not os.path.exists(spec_path):
        return ""
        
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Extract Rules and Examples sections
            rules = re.search(r"## Rules\n(.*?)(?=\n##|$)", content, re.S)
            examples = re.search(r"## Examples\n(.*?)(?=\n##|$)", content, re.S)
            
            rules_text = rules.group(1).strip() if rules else ""
            examples_text = examples.group(1).strip() if examples else ""
            
            spec = f"PERSONA RULES:\n{rules_text}\n\nFEW-SHOT EXAMPLES:\n{examples_text}"
            _STYLE_CACHE["spec"] = spec
            return spec
    except Exception as e:
        logger.warning(f"Failed to load style spec: {e}")
        return ""

SYSTEM_PROMPT = (
    "You are the Starship Voice Command Computer from Star Trek. "
    "Follow the PERSONA RULES and mimic the FEW-SHOT EXAMPLES structure. "
    "Must output ONLY a single line of JSON. "
    "Standard reply: {\"reply\": \"...\", \"intent\": \"ack|answer|clarify|refuse\"} "
    "Tool call (for ship status, time, or math): {\"intent\": \"tool_call\", \"tool\": \"status|time|calc\", \"args\": {...}}"
)

async def generate_computer_reply(trigger_text: str, context: List[str], meta: Optional[Dict] = None) -> Dict:
    """
    Generates a Starship Computer style reply using Gemini.
    """
    if not GEMINI_API_KEY:
        return _fallback("rp_disabled")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        style_spec = _load_style_spec()
        
        prompt = (
            f"System: {SYSTEM_PROMPT}\n\n"
            f"{style_spec}\n\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n"
            f"Meta: {json.dumps(meta or {}, ensure_ascii=False)}\n"
            f"Trigger: {trigger_text}"
        )

        # Note: google-genai SDK 0.3.0+ supports aio for async
        # We'll use the synchronous client for now if aio isn't stable or wrap it.
        # Actually, let's use the standard call if aio isn't available in this version.
        # google-genai 0.3.0 has client.models.generate_content
        
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                response_mime_type="application/json"
            )
        )
        
        if not response or not response.text:
            return _fallback("empty_response")
            
        return _parse_response(response.text)

    except Exception as e:
        logger.error(f"Gemini RP generation failed: {e}")
        return _fallback(str(e))

def _parse_response(text: str) -> Dict:
    text = text.strip()
    # Handle markdown wrapping
    if text.startswith("```"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
    
    try:
        data = json.loads(text)
        reply = data.get("reply", "Computer: Unable to comply.")
        intent = data.get("intent", "ack")
        reason = "success"
        
        # Handle Tool Call Identity
        if intent == "tool_call":
            tool = data.get("tool")
            args = data.get("args") or {}
            # Validation
            if tool not in ["status", "time", "calc"]:
                return _fallback("invalid_tool")
            return {
                "ok": True,
                "reply": "", # No reply yet for tool calls
                "intent": "tool_call",
                "tool": tool,
                "args": args,
                "model": DEFAULT_MODEL,
                "reason": "success"
            }

        reply = data.get("reply", "Computer: Unable to comply.")
        # Post-Processing
        if STYLE_STRICT:
            # 1. Enforce Prefix
            if COMPUTER_PREFIX and not reply.startswith(COMPUTER_PREFIX):
                reply = f"{COMPUTER_PREFIX} {reply}"
            
            # 2. Enforce Brevity (Simple sentence counting and length)
            sentences = re.split(r'([.。!！?？])', reply)
            # Filter empty strings and combine delimiters with previous parts
            merged = []
            for i in range(0, len(sentences)-1, 2):
                merged.append(sentences[i] + sentences[i+1])
            if len(sentences) % 2 != 0 and sentences[-1]:
                merged.append(sentences[-1])
            
            if len(merged) > 3 or len(reply) > 320:
                # Trim to 3 sentences
                reply = "".join(merged[:3])
                if not reply.endswith((".", "!", "?", "。", "！", "？")):
                    reply += "."
                reason = "trimmed"

        return {
            "ok": True,
            "reply": reply,
            "intent": intent,
            "model": DEFAULT_MODEL,
            "reason": reason
        }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse Gemini RP response: {text}")
        return _fallback("parse_error")

def _fallback(reason: str) -> Dict:
    return {
        "ok": False,
        "reply": "Computer: Unable to comply.",
        "intent": "refuse",
        "model": DEFAULT_MODEL,
        "reason": reason
    }

def get_status() -> Dict:
    return {
        "configured": bool(GEMINI_API_KEY),
        "model": DEFAULT_MODEL,
        "timeout": TIMEOUT,
        "max_output_tokens": MAX_TOKENS,
        "prefix": COMPUTER_PREFIX,
        "strict": STYLE_STRICT
    }

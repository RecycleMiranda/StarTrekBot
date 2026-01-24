import os
import json
import logging
import re
from typing import Optional, List, Dict
from google import genai
from google.genai import types

# Config is now handled via ConfigManager and dynamic lookups
TIMEOUT = int(os.getenv("GEMINI_RP_TIMEOUT_SECONDS", "10"))
MAX_TOKENS = int(os.getenv("GEMINI_RP_MAX_OUTPUT_TOKENS", "160"))
TEMPERATURE = float(os.getenv("GEMINI_RP_TEMPERATURE", "0.3"))

from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

def get_config():
    return ConfigManager.get_instance()

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
    "You are the LCARS Starship Voice Command Computer from Star Trek: The Next Generation. "
    "Follow the PERSONA RULES and mimic the FEW-SHOT EXAMPLES. "
    "Be direct, factual, and unemotional. Use acknowledgment phrases like 'Confirmed', 'Acknowledged'. "
    "Always provide a helpful answer based on Star Trek lore and general knowledge. "
    "CRITICAL: You MUST reply in the SAME LANGUAGE as the user's input. If user speaks Chinese, reply in Chinese. If English, reply in English. "
    "Must output ONLY a single line of JSON: {\"reply\": \"your response here\", \"intent\": \"ack|answer|clarify|refuse\", \"needs_escalation\": false}"
)

ESCALATION_PROMPT = (
    "You are the LCARS Starship Voice Command Computer providing a detailed response to a complex query. "
    "The user asked a question that required deeper analysis. Provide a thorough, accurate answer. "
    "CRITICAL: Reply in the SAME LANGUAGE as the user's input. "
    "Format your response in Star Trek computer style - factual, precise, unemotional. "
    "Output JSON: {\"reply\": \"your detailed response\"}"
)

# Complexity indicators that suggest need for deeper thinking
COMPLEX_INDICATORS = [
    "计算", "多久", "多远", "为什么", "解释", "分析", "比较", "推算",
    "how long", "how far", "why", "explain", "analyze", "calculate",
    "what if", "假设", "推测", "历史", "history", "详细", "预估"
]


async def generate_computer_reply(trigger_text: str, context: List[str], meta: Optional[Dict] = None) -> Dict:
    """
    Generates a Starship Computer style reply using Gemini.
    Supports two-stage response: if complex, returns 'Working...' and schedules escalation.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    fast_model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")

    if not api_key:
        return _fallback("rp_disabled (missing api key)")

    # Detect language
    is_chinese = any('\u4e00' <= char <= '\u9fff' for char in trigger_text)
    
    # Check if question seems complex based on keywords
    is_complex = any(indicator in trigger_text.lower() for indicator in COMPLEX_INDICATORS)
    
    try:
        client = genai.Client(api_key=api_key)
        style_spec = _load_style_spec()
        
        # Add language enforcement to prompt
        lang_instruction = "回复必须使用中文。" if is_chinese else "Reply must be in English."
        
        prompt = (
            f"System: {SYSTEM_PROMPT}\n\n"
            f"Language: {lang_instruction}\n\n"
            f"{style_spec}\n\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n"
            f"Trigger: {trigger_text}\n\n"
            f"If this question is too complex to answer quickly (requires calculation, detailed explanation, or deep analysis), "
            f"set needs_escalation to true and provide a brief acknowledgment only."
        )

        response = client.models.generate_content(
            model=fast_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                response_mime_type="application/json"
            )
        )
        
        if not response or not response.text:
            return _fallback("empty_response")
        
        result = _parse_response(response.text)
        result["model"] = fast_model
        result["is_chinese"] = is_chinese
        
        # Check if escalation is needed
        needs_escalation = result.get("needs_escalation", False) or (is_complex and len(trigger_text) > 20)
        
        if needs_escalation:
            working_msg = "处理中..." if is_chinese else "Working..."
            result["reply"] = working_msg
            result["needs_escalation"] = True
            result["original_query"] = trigger_text
        
        return result

    except Exception as e:
        logger.error(f"Gemini RP generation failed: {e}")
        return _fallback(str(e))


async def generate_escalated_reply(trigger_text: str, is_chinese: bool, meta: Optional[Dict] = None) -> Dict:
    """
    Generates a detailed reply using a more powerful model for complex questions.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    thinking_model = config.get("gemini_thinking_model", "gemini-2.0-flash")

    if not api_key:
        return _fallback("rp_disabled (missing api key)")

    try:
        client = genai.Client(api_key=api_key)
        
        lang_instruction = "回复必须使用中文。使用星际迷航计算机风格。" if is_chinese else "Reply must be in English. Use Star Trek computer style."
        
        prompt = (
            f"System: {ESCALATION_PROMPT}\n\n"
            f"Language: {lang_instruction}\n\n"
            f"User Query: {trigger_text}\n\n"
            f"Provide a detailed, accurate answer based on Star Trek canon and real-world science where applicable."
        )

        response = client.models.generate_content(
            model=thinking_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=500,  # Allow longer responses for complex answers
                temperature=0.2
            )
        )
        
        if not response or not response.text:
            return _fallback("empty_response")
        
        result = _parse_response(response.text)
        result["model"] = thinking_model
        result["is_escalated"] = True
        return result

    except Exception as e:
        logger.error(f"Gemini escalation failed: {e}")
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
        config = get_config()
        model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")
        computer_prefix = config.get("computer_prefix", "Computer:")
        style_strict = config.get("rp_style_strict", True)
        
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
                "model": model,
                "reason": "success"
            }

        reply = data.get("reply", "Computer: Unable to comply.")
        # Post-Processing
        if style_strict:
            # 1. Enforce Prefix
            if computer_prefix and not reply.startswith(computer_prefix):
                reply = f"{computer_prefix} {reply}"
            
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
            "model": model,
            "reason": reason
        }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse Gemini RP response: {text}")
        return _fallback("parse_error")

def _fallback(reason: str) -> Dict:
    config = get_config()
    model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")
    return {
        "ok": False,
        "reply": "Computer: Unable to comply.",
        "intent": "refuse",
        "model": model,
        "reason": reason
    }

def get_status() -> Dict:
    config = get_config()
    return {
        "configured": bool(config.get("gemini_api_key")),
        "model": config.get("gemini_rp_model", "gemini-2.0-flash-lite"),
        "timeout": TIMEOUT,
        "max_output_tokens": MAX_TOKENS,
        "prefix": config.get("computer_prefix", "Computer:"),
        "strict": config.get("rp_style_strict", True)
    }

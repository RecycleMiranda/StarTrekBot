import os
import json
import logging
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

SYSTEM_PROMPT = (
    "You are the Starship Voice Command Computer from Star Trek."
    "Respond in a concise, technical, and efficient manner."
    "Keep replies to 1-2 sentences. If clarifying, ask only one question."
    "No long explanations. No lists over 3 items."
    "Must output ONLY a single line of JSON: {\"reply\": \"...\", \"intent\": \"ack|answer|clarify|refuse\"}."
)

async def generate_computer_reply(trigger_text: str, context: List[str], meta: Optional[Dict] = None) -> Dict:
    """
    Generates a Starship Computer style reply using Gemini.
    """
    if not GEMINI_API_KEY:
        return _fallback("rp_disabled")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = (
            f"System: {SYSTEM_PROMPT}\n\n"
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
        return {
            "ok": True,
            "reply": data.get("reply", "Computer: Unable to comply."),
            "intent": data.get("intent", "ack"),
            "model": DEFAULT_MODEL,
            "reason": "success"
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
        "max_output_tokens": MAX_TOKENS
    }

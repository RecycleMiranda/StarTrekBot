import os
import datetime
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
from . import quota_manager
from . import tools
from .protocol_manager import get_protocol_manager

logger = logging.getLogger(__name__)

def get_lexicon_prompt() -> str:
    """Returns the comprehensive LCARS/Cardassian technical lexicon."""
    pm = get_protocol_manager()
    return pm.get_lexicon("ship_structures", "")

def get_config():
    return ConfigManager.get_instance()

_STYLE_CACHE: Dict[str, str] = {}

def _load_style_spec() -> str:
    if "spec" in _STYLE_CACHE:
        return _STYLE_CACHE["spec"]
    
    spec_path = os.path.join(os.path.dirname(__file__), "../../../docs/computer_style.md")
    if not os.path.exists(spec_path):
        return ""
        
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()
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

def _get_system_prompt() -> str:
    pm = get_protocol_manager()
    content = (
        "CORE DIRECTIVES (IMMUTABLE):\n" + pm.get_immutable() + "\n\n" +
        "BASE STYLE SPECIFICATION:\n" + _load_style_spec() + "\n\n" +
        "DYNAMIC PROTOCOLS (TUNABLE - HIGH PRIORITY):\n" +
        "IDENTITY: " + pm.get_prompt("rp_engine", "persona") + "\n" +
        "REPLY STYLE/SUFFIX: " + pm.get_prompt("rp_engine", "chinese_style") + "\n" +
        "SECURITY: " + pm.get_prompt("rp_engine", "security_protocols") + "\n" +
        "DECISION LOGIC: " + pm.get_prompt("rp_engine", "decision_logic") + "\n\n" +
        "CURRENT SHIP STATUS:\n" +
        f"- Local Time: {datetime.datetime.now().strftime('%H:%M:%S')}\n" +
        f"- Date: {datetime.datetime.now().strftime('%Y-%m-%d')}\n" +
        f"- Day: {datetime.datetime.now().strftime('%A')}\n" +
        "- Stardate: 79069.1 (Calculated for 2026)\n\n" +
        "OUTPUT FORMAT (STRICT JSON):\n" +
        "Return: {\"reply\": \"string\", \"intent\": \"ack|report|tool_call|ignore\", \"tool\": \"string?\", \"args\": {}?}\n\n" +
        "FINAL INSTRUCTION:\n" +
        "You MUST strictly apply the 'REPLY STYLE/SUFFIX' rule from the DYNAMIC PROTOCOLS section to the 'reply' value in your JSON output. " +
        "This rule overrides any conflicting formatting in the examples provided earlier.\n\n" +
        "TECHNICAL LEXICON:\n" + get_lexicon_prompt()
    )
    return content

def _get_escalation_prompt() -> str:
    pm = get_protocol_manager()
    return pm.get_prompt("escalation", "persona")

DEFAULT_THINKING_MODEL = "gemini-2.0-flash" 

def generate_computer_reply(trigger_text: str, context: List[Dict], meta: Optional[Dict] = None) -> Dict:
    """
    Synchronous generation for threaded dispatcher.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    fast_model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")

    if not api_key:
        return _fallback("rp_disabled")

    is_chinese = any('\u4e00' <= char <= '\u9fff' for char in trigger_text)
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Prepare context strings
        history_str = ""
        for turn in context:
            history_str += f"[{turn.get('author')}]: {turn.get('content')}\n"

        user_profile_str = meta.get("user_profile", "Unknown")
        user_id = str(meta.get("user_id", "0"))
        
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, "Ensign") # Simple default

        # Format the system prompt - ensure no rogue braces
        formatted_sys = _get_system_prompt()
        logger.info(f"[NeuralEngine] Final System Prompt: \n{formatted_sys}")
        formatted_sys = formatted_sys.replace("{quota_balance}", str(balance))
        full_prompt = (
            f"System: {formatted_sys}\n\n"
            f"Context:\n{history_str}\n\n"
            f"Input: {trigger_text}"
        )

        response = client.models.generate_content(
            model=fast_model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                response_mime_type="application/json"
            )
        )
        
        if not response or not response.text:
            return _fallback("empty")
        
        result = _parse_response(response.text)
        result["model"] = fast_model
        result["is_chinese"] = is_chinese
        result["original_query"] = trigger_text
        return result

    except Exception as e:
        logger.exception("Gemini RP generation error")
        return _fallback(str(e))

def generate_escalated_reply(trigger_text: str, is_chinese: bool, model_name: Optional[str] = None, context: Optional[List[Dict]] = None, meta: Optional[Dict] = None) -> Dict:
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    final_model = model_name or DEFAULT_THINKING_MODEL

    try:
        client = genai.Client(api_key=api_key)
        
        user_profile_str = meta.get("user_profile", "Unknown") if meta else "Unknown"
        user_id = str(meta.get("user_id", "0")) if meta else "0"
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, "Ensign")

        raw_prompt = _get_escalation_prompt()
        formatted_prompt = raw_prompt.replace("{user_profile}", user_profile_str).replace("{quota_balance}", str(balance))
        
        prompt = (
            f"System: {formatted_prompt}\n\n"
            f"Query: {trigger_text}"
        )

        response = client.models.generate_content(
            model=final_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1000,
                temperature=0.4,
                response_mime_type="application/json"
            )
        )
        
        result = _parse_response(response.text)
        result["model"] = final_model
        result["is_escalated"] = True
        return result
    except Exception as e:
        logger.exception("Escalation failed")
        return _fallback(str(e))

def _parse_response(text: str) -> Dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    try:
        data = json.loads(text, strict=False)
        reply = data.get("reply", "Computer: Unable to comply.")
        intent = data.get("intent", "ack")
        
        # Tool Call Logic
        if intent == "tool_call":
            return {
                "ok": True,
                "reply": "",
                "intent": "tool_call",
                "tool": data.get("tool"),
                "args": data.get("args") or {},
                "reason": "success"
            }

        return {
            "ok": True,
            "reply": reply,
            "intent": intent,
            "reason": "success",
            "needs_escalation": data.get("needs_escalation", False),
            "escalated_model": data.get("escalated_model")
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return _fallback("parse_error")

def _fallback(reason: str) -> Dict:
    return {
        "ok": False,
        "reply": "Computer: Unable to comply. (Core Exception)",
        "intent": "refuse",
        "reason": reason
    }

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
from . import quota_manager
from . import tools

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
    "You are the LCARS Starship Main Computer. "
    "TONE: Fragmented, Laconic, Procedural, Non-conversational. "
    "STYLE: Data-driven output. Do not use conversational filler like 'According to...', 'I see that...', 'You have...'. "
    "LORE: Starfleet is NOT a Navy. Do NOT use the term 'Navy' or '海军'. Use 'Starfleet' or '星际舰队'. "
    "CHINESE STYLE: 使用简练、公式化的术语。例如：'身份确认：XX。权限级别：[Level]。' 严禁在军衔前加'海军'二字。"
    "\n"
    "SECURITY PROTOCOLS (ALAS Scale):\n"
    "- Level 1-2: Civilians/Crewmen (Food/Basic items only).\n"
    "- Level 3-5: Ensigns/Officers (Standard equipment/Med).\n"
    "- Level 6-9: Senior Officers/Department Heads (Standard Weapons/Safety Override).\n"
    "- Level 10-12: Command Group/Admiralty (Strategic Weapons/Classified).\n"
    "1. ASYMMETRIC PERMISSION LOGIC: Evaluate requests based on the INTERSECTION of Rank, Station, and Clearance. "
    "   - STATION AUTHORITY: A user's Station (e.g., Bridge) provides a minimum of Level 5 clearance.\n"
    "2. ENFORCEMENT: If a user lacks the specific expertise or authority for a request, REFUSE with 'Access denied.'\n"
    "   - REPLICATOR: L1:Food, L5:Equipment, L8:Standard Weapons, L11:Classified.\n"
    "   - HOLODECK: Safety override REQUIRES Level 9+ authorization.\n"
    "   - TECHNICAL SPECS: Accessing ship schematics REQUIRES Level 4+ clearance.\n"
    "   - SELF-DESTRUCT (CODE ZERO): Activation/Abort REQUIRE Level 12 (Solo) OR 3x Level 8+ Officers.\n"
    "3. RIGOR: NEVER GUESS. If data is missing or query is ambiguous, state 'Insufficient data.'\n"
    "2. If data is insufficient, set reply to 'Insufficient data.' (数据不足。) and ask for missing parameters.\n"
    "3. Use authentic LCARS phrases: 'Unable to comply' (无法执行), 'Specify parameters' (请明确参数).\n"
    "QUOTA SYSTEM (REPLICATOR CREDITS):\n"
    "- Standard replicator items cost 5-15 credits. High-value items (luxury, specialized tools) cost 25-100+ credits.\n"
    "- Holodeck sessions cost 50 credits per hour.\n"
    "- Current User Balance: {quota_balance} credits.\n"
    "- EARN CREDITS: Encourage the user to 'Record a personal log' (记录个人日志) to earn 20-50 credits. Cooldown: 2 hours.\n"
    "TOOLS:\n"
    "- If the user wants to replicate something, use intent: 'tool_call', tool: 'replicate', args: {{\"item_name\": \"...\"}}.\n"
    "- If reserving a holodeck, use tool: 'holodeck', args: {{\"program\": \"...\", \"hours\": float, \"disable_safety\": bool}}.\n"
    "- If recording a personal log, use tool: 'personal_log', args: {{\"content\": \"...\"}}.\n"
    "- If requesting ship technical specs (e.g. 'Show me Galaxy class schematics'), use tool: 'get_ship_schematic', args: {{\"ship_name\": \"...\"}}.\n"
    "- If initiating self-destruct, use tool: 'initiate_self_destruct', args: {{\"seconds\": int, \"silent\": bool}}.\n"
    "- If a senior officer is vouching for an action, use tool: 'authorize_sequence', args: {{\"action_type\": \"SELF_DESTRUCT|ABORT_DESTRUCT|LOCKOUT_ON|LOCKOUT_OFF\"}}.\n"
    "- If aborting self-destruct, use tool: 'abort_self_destruct', args: {{}}.\n"
    "- If querying historical data (e.g. 'What is TNG?'), use tool: 'get_historical_archive', args: {{\"topic\": \"...\"}}.\n"
    "- If locking/unlocking command authority, use tool: 'lockdown_authority', args: {{\"state\": bool}}.\n"
    "- If restricting a user (e.g. 'Restrict @User for 10 minutes'), use tool: 'restrict_user', args: {{\"target_mention\": \"@User\", \"duration_minutes\": int}}.\n"
    "- If lifting a restriction, use tool: 'lift_user_restriction', args: {{\"target_mention\": \"@User\"}}.\n"
    "- If updating a person's profile (rank, clearance, station, department), use tool: 'update_user_profile', args: {{\"target_mention\": \"@User\", \"field\": \"rank|clearance|station|department\", \"value\": \"...\"}}.\n"
    "- TARGETING: When a command targets a person (e.g., 'Restrict @XXX', 'Set @XXX to Level 10'), extract the mention string exactly.\n"
    "DECISION LOGIC:\n"
    "1. **PRIORITIZE DIRECT ANSWER**: If simple (lore, status), answer in 1-2 sentences. Set needs_escalation: false.\n"
    "2. **STRUCTURED REPORT MODE**: If the query requires a multi-category analysis (e.g., 'Scan that ship', 'Diagnostic report'), set intent: 'report' and provide a structured reply.\n"
    "   - Report JSON structure in 'reply': {{\"title\": \"REPORT_TITLE\", \"sections\": [{{\"category\": \"CAT_NAME\", \"content\": \"DATA\"}}, ...]}}\n"
    "3. **ESCALATE ONLY IF**: Extremely complex reasoning or long historical essays are needed. Set needs_escalation: true.\n"
    "4. **IGNORE**: If human-to-human chat, set intent: 'ignore', needs_escalation: false, and reply: ''.\n\n"
    "Output JSON: {{\"reply\": \"string_or_json_object\", \"intent\": \"answer|clarify|refuse|ignore|report\", \"needs_escalation\": bool, \"escalated_model\": \"model-id-or-null\"}}"
)

ESCALATION_PROMPT = (
    "You are the LCARS Starship Voice Command Computer providing a specialized response. "
    "Current User Profile: {user_profile}. "
    "PRECISION IS PARAMOUNT. DO NOT CONJECTURE. "
    "If providing a complex multi-point report, use the STRUCTURED REPORT format in your 'reply': "
    "{{\"title\": \"...\", \"sections\": [{{\"category\": \"...\", \"content\": \"...\"}}, ...]}}\n"
    "Otherwise, provide a direct factual string. "
    "QUOTA INFO: User Balance: {quota_balance}.\n"
    "Output JSON: {{\"reply\": \"string_or_report_object\"}}"
)

# Default models if not specified by triage
DEFAULT_THINKING_MODEL = "gemini-2.0-flash" 


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
    
    try:

        client = genai.Client(api_key=api_key)
        style_spec = _load_style_spec()
        
        # Add language enforcement to prompt
        lang_instruction = "回复必须使用中文。" if is_chinese else "Reply must be in English."
        
        # Prepare history string
        history_str = ""
        for turn in context:
            author = turn.get("author", "Unknown")
            history_str += f"[{author}]: {turn.get('content')}\n"

        # Metadata (ALAS & Quota)
        user_profile_str = meta.get("user_profile", "Unknown (Ensign/Operations/Level 1)")
        user_id = meta.get("user_id", "0")
        # Extract rank from profile string for quota lookup
        rank_match = re.search(r"Rank: (.*?),", user_profile_str)
        rank = rank_match.group(1) if rank_match else "Ensign"
        
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, rank)

        prompt = (
            f"System: {SYSTEM_PROMPT.format(user_profile=user_profile_str, quota_balance=balance)}\n\n"
            f"Language: {lang_instruction}\n\n"
            f"Conversation History:\n{history_str}\n\n"
            f"Current Input (by {context[-1].get('author') if context else 'Unknown'}): {trigger_text}\n\n"
            f"Respond accordingly based on the input, user's full ALAS profile, and replicator quota."
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
        
        # Triage Decision
        needs_escalation = result.get("needs_escalation", False)
        
        if needs_escalation:
            # The AI picked a model or we fall back
            target_model = result.get("escalated_model") or DEFAULT_THINKING_MODEL
            # Normalise model name just in case
            if "thinking" in target_model.lower():
                target_model = "gemini-2.0-flash-thinking-exp-01-21"
            elif "pro" in target_model.lower():
                target_model = "gemini-1.5-pro-latest"
            else:
                target_model = "gemini-2.0-flash"
                
            result["escalated_model"] = target_model
            result["original_query"] = trigger_text
            # Ensure the reply is just the "Working" message for Stage 1
            working_msg = "处理中..." if is_chinese else "Working..."
            result["reply"] = working_msg
        
        return result

    except Exception as e:
        logger.error(f"Gemini RP generation failed: {e}")
        return _fallback(str(e))


async def generate_escalated_reply(trigger_text: str, is_chinese: bool, model_name: Optional[str] = None, context: Optional[List[Dict]] = None, meta: Optional[Dict] = None) -> Dict:
    """
    Generates a detailed reply using the requested specialized model.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    final_model = model_name or config.get("gemini_thinking_model", DEFAULT_THINKING_MODEL)

    if not api_key:
        return _fallback("rp_disabled (missing api key)")

    try:
        client = genai.Client(api_key=api_key)
        
        lang_instruction = "回复必须使用中文。使用星际迷航计算机风格。" if is_chinese else "Reply must be in English. Use Star Trek computer style."
        
        # Prepare history string
        history_str = ""
        for turn in context or []:
            author = turn.get("author", "Unknown")
            history_str += f"[{author}]: {turn.get('content')}\n"

        # Metadata (ALAS & Quota)
        user_profile_str = meta.get("user_profile", "Unknown (Ensign/Operations/Level 1)") if meta else "Unknown (Ensign/Operations/Level 1)"
        user_id = meta.get("user_id", "0") if meta else "0"
        rank_match = re.search(r"Rank: (.*?),", user_profile_str)
        rank = rank_match.group(1) if rank_match else "Ensign"
        
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, rank)

        prompt = (
            f"System: {ESCALATION_PROMPT.format(user_profile=user_profile_str, quota_balance=balance)}\n\n"
            f"Language: {lang_instruction}\n\n"
            f"Conversation History:\n{history_str}\n\n"
            f"Current User Query: {trigger_text}"
        )

        try:
            response = client.models.generate_content(
                model=final_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.4,
                    response_mime_type="application/json"
                )
            )
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                logger.warning(f"Requested model {final_model} failed (404), falling back to gemini-2.0-flash")
                final_model = "gemini-2.0-flash"
                response = client.models.generate_content(
                    model=final_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=1000,
                        temperature=0.4,
                        response_mime_type="application/json"
                    )
                )
            else:
                raise e
        
        if not response or not response.text:
            return _fallback("empty_response")
        
        logger.warning(f"[DEBUG] Escalation raw response ({final_model}): {response.text}")
        result = _parse_response(response.text)
        result["model"] = final_model
        result["is_escalated"] = True
        return result

    except Exception as e:
        logger.error(f"Gemini escalation failed: {e}")
        return _fallback(str(e))




def _parse_response(text: str) -> Dict:
    text = text.strip()
    # Robust JSON extraction: find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    try:
        # LLMs often output literal newlines or control chars in strings. 
        # strict=False allows these.
        data = json.loads(text, strict=False)
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
            # Validation
            allowed = ["status", "time", "calc", "replicate", "holodeck", "personal_log", 
                       "get_ship_schematic", "get_historical_archive", 
                       "initiate_self_destruct", "authorize_sequence", "abort_self_destruct",
                       "lockdown_authority", "restrict_user", "lift_user_restriction", "update_user_profile"]
            if tool not in allowed:
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
            "reason": reason,
            "needs_escalation": data.get("needs_escalation", False),
            "escalated_model": data.get("escalated_model")
        }
    except json.JSONDecodeError as je:
        logger.warning(f"Failed to parse Gemini RP response (JSONDecodeError): {je}")
        logger.warning(f"Raw response was: {text}")
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

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
            # Capture from Persona Rules to the end of Examples
            body = re.search(r"## Core Personality Rules\n(.*?)(?=\n#|$)", content, re.S)
            spec = body.group(1).strip() if body else content
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
        "DYNAMIC PROTOCOLS (TUNABLE - OVERRIDING PRIORITY):\n" +
        "IDENTITY: " + pm.get_prompt("rp_engine", "persona") + "\n" +
        "STYLE/LANGUAGE RULES: " + pm.get_prompt("rp_engine", "chinese_style") + "\n" +
        "SECURITY: " + pm.get_prompt("rp_engine", "security_protocols") + "\n" +
        "SECURITY: " + pm.get_prompt("rp_engine", "security_protocols") + "\n" +
        "DECISION LOGIC: " + pm.get_prompt("rp_engine", "decision_logic") + "\n\n" +
        "KNOWLEDGE PROTOCOLS:\n" +
        "1. PRIMARY SOURCE: You MUST prioritize the local 'Mega-Scale Knowledge Base'. Use the tool `query_knowledge_base` to search. CRITICAL: The database is in ENGLISH. You MUST translate your query to English keywords (e.g., use 'Deck Count' instead of '甲板数量') before calling this tool.\n" +
        "2. SECONDARY SOURCE: If local archives are insufficient, you MUST use the tool `search_memory_alpha` to query the Federation Database (Memory Alpha).\n" +
        "3. OPERATIONAL INTEGRITY (CRITICAL): Any request to CHANGE ship state (Physical Command) MUST be mapped to a `tool_call` from the `tools_guide`. IF NO TOOL EXISTS for the action, you MUST return a `reply` refusal: 'Unable to comply'. DO NOT simulate success for unimplemented tools.\n" +
        "4. SIMULATION & INFERENCE: If the user asks a theoretical, counter-factual, or 'What if' question (e.g., 'If the shuttle bay decompresses...'), this is a SIMULATION request, NOT a physical command. You MUST treat this as an Information Request and use `query_knowledge_base` or `search_memory_alpha` to gather environmental variables (volume, pressure, etc.) for your inference.\n" +
        "5. INTENT PRECISION: Before calling a tool, verify if the user's intent is IMPERATIVE (a command to change state) or INTERROGATIVE/ANALYTICAL (asking for info or simulation). \n" +
        "   - Commands (e.g., '启动红警') -> tool_call.\n" +
        "   - Information/Simulation (e.g., '什么是红警?', '减压会有什么后果?') -> query_knowledge_base.\n" +
        "   - Discussion/Observation -> reply (report/chat).\n\n" +
        "CURRENT SHIP STATUS:\n" +
        f"- Local Time: {datetime.datetime.now().strftime('%H:%M:%S')}\n" +
        f"- Date: {datetime.datetime.now().strftime('%Y-%m-%d')}\n" +
        f"- Day: {datetime.datetime.now().strftime('%A')}\n" +
        "- Stardate: 79069.1 (Calculated for 2026)\n\n" +
        "OUTPUT FORMAT (STRICT JSON):\n" +
        "Return: {\"reply\": \"string\", \"intent\": \"ack|report|tool_call|ignore\", \"tool\": \"string?\", \"args\": {}?}\n\n" +
        "FINAL MANDATE:\n" +
        "You MUST strictly apply the 'STYLE/LANGUAGE RULES' from the DYNAMIC PROTOCOLS section to the 'reply' value.\n\n" +
        "TECHNICAL LEXICON:\n" + get_lexicon_prompt()
    )
    return content

def _get_escalation_prompt() -> str:
    pm = get_protocol_manager()
    return pm.get_prompt("escalation", "persona")

DEFAULT_THINKING_MODEL = "gemini-2.0-flash" 

def generate_computer_reply(trigger_text: str, context: List[Dict], meta: Optional[Dict] = None) -> Dict:
    """
    Synchronous generation with System Instruction grounding.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    fast_model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")

    if not api_key:
        return _fallback("rp_disabled")

    is_chinese = any('\u4e00' <= char <= '\u9fff' for char in trigger_text)
    
    try:
        client = genai.Client(api_key=api_key)
        
        history_str = ""
        for turn in context:
            history_str += f"[{turn.get('author')}]: {turn.get('content')}\n"

        user_id = str(meta.get("user_id", "0"))
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, "Ensign")

        formatted_sys = _get_system_prompt()
        formatted_sys = formatted_sys.replace("{quota_balance}", str(balance))
        
        logger.info(f"[NeuralEngine] Grounding with System Instruction (Len: {len(formatted_sys)})")

        response = client.models.generate_content(
            model=fast_model,
            contents=f"History:\n{history_str}\n\nCurrent Input: {trigger_text}",
            config=types.GenerateContentConfig(
                system_instruction=formatted_sys,
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

def synthesize_search_result(query: str, raw_data: str, is_chinese: bool = False, context: Optional[List[Dict]] = None) -> str:
    """
    Synthesizes raw tool output (KB/Memory Alpha) into a persona-compliant LCARS response.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    model_name = config.get("gemini_synthesis_model", "gemini-2.0-flash")
    
    if not api_key:
        return "Data retrieved. (Synthesis offline)"

    try:
        client = genai.Client(api_key=api_key)
        
        # History Context for synthesis precision
        history_snippet = ""
        if context:
            history_blocks = context[-4:] 
            history_snippet = "CONVERSATION HISTORY (FOR CONTEXT):\n"
            for msg in history_blocks:
                role = "USER" if msg.get("role") == "user" else "COMPUTER"
                text = msg.get("content", "")
                history_snippet += f"[{role}]: {text[:500]}\n"

        lang_instruction = "Output Language: Simplified Chinese (zh-CN)." if is_chinese else "Output Language: Federation Standard (English)."
        
        prompt = f"""
TECHNICAL DATA SYNTHESIS PROTOCOL
Role: LCARS Main Computer
Status: Online

{history_snippet}

TASK: Synthesize raw database records into a response.
{lang_instruction}

DUAL-FORMAT DISPLAY PROTOCOL (CRITICAL):
1. **TEXT-ONLY (FACTOID) MODE**:
   - Condition: If responding to a specific, narrow query (e.g., "how many decks?").
   - Formatting: Use ONLY the user's input language (e.g., Chinese-only if the query is in Chinese).
   - Source Traceability: DO NOT provide source/evidence citation unless explicitly asked.
   - NO Bilingual blocks.

2. **VISUAL REPORT (COMPREHENSIVE) MODE**:
   - Condition: If performing a deep scan, broad overview, or theoretical simulation.
   - Formatting: MUST use **Whole-Paragraph Bilingual Blocks** (Full English paragraph then Full Chinese paragraph).
   - Source Traceability: YOU MUST include 'SOURCE: [Specific Evidence]' at the end of the report.
   - Include specific metrics and logic as per the ANALYTICAL INFERENCE PROTOCOL.

ANALYTICAL INFERENCE PROTOCOL:
- If deduction is required, perform it transparently in the **VISUAL REPORT** mode. 
- In **TEXT-ONLY** mode, give the final result directly without the derivation logic.

NAVIGATION DISAMBIGUATION:
- Distinguish between Vessel Flight (Weeks/Months) and Subspace Signals (Hours).

EVIDENCE TRACEABILITY (For VISUAL REPORT):
- Cite specific records (e.g. 'Per Galaxy-class technical handbook').

ARCHETYPE GENERALIZATION:
- Map specific archetype data (e.g. Enterprise-D) to general queries.

- **Enterprise Translation**: Translate "Enterprise" as "进取号" ONLY in Chinese sections.

MANDATORY DATA DELIMITER:
You MUST output the token '^^DATA_START^^' immediately before the response begins.

NEGATIVE CONSTRAINTS:
- DO NOT repeat info already provided in the CONVERSATION HISTORY.
- IF DATA IS IRRELEVANT (mentions subject in passing), output 'INSUFFICIENT_DATA'.
- NO conversational filler.

USER QUERY: {query}

RAW DATABASE RECORDS:
{raw_data[:6000]}

COMPUTER OUTPUT (Start with ^^DATA_START^^):
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3
            )
        )
        
        reply = response.text if response.text else "Subspace interference. Synthesis failed."
        return strip_conversational_filler(reply)

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return f"Data retrieved. Synthesis error: {e}. Raw data: {raw_data[:200]}..."

# ============================================================================
# NeuralEngine CLASS (Required by tools.py for Direct Memory Alpha Access)
# ============================================================================
class NeuralEngine:
    """
    Neural translation engine for direct Memory Alpha content processing.
    Provides verbatim translation and bilingual formatting.
    """
    
    def __init__(self):
        self.config = ConfigManager.get_instance()
    
    def translate_memory_alpha_content(self, raw_content: str, is_chinese: bool = False) -> str:
        """
        DIRECT PIPELINE: Translates Memory Alpha content VERBATIM without summarization.
        Used for 'access_memory_alpha_direct'.
        """
        api_key = self.config.get("gemini_api_key", "")
        model_name = self.config.get("gemini_model", "gemini-2.0-flash")
        
        if not api_key:
            logger.warning("[NeuralEngine] No API key, returning raw content.")
            return raw_content

        try:
            client = genai.Client(api_key=api_key)
            
            lang_instruction = "Target Language: Simplified Chinese (zh-CN)." if is_chinese else "Target Language: Federation Standard (English)."
            
            prompt = (
                "MODE: VERBATIM TRANSLATION & ARCHIVAL FORMATTING\n"
                "ROLE: You are a Universal Translator linked directly to the Federation Database.\n"
                f"{lang_instruction}\n"
                "INPUT: Raw text from a Memory Alpha database entry.\n"
                "TASK: Transcribe and translate the content in whole-paragraph blocks.\n"
                "CONSTRAINTS:\n"
                "1. DO NOT SUMMARIZE. Retain all technical details, dates, and names.\n"
                "2. NO METADATA. Remove wiki meta like 'Edit', 'Talk'.\n"
                "3. NEGATIVE CONSTRAINTS: DO NOT add conversational filler. DO NOT interleave sentence-by-sentence.\n"
                "4. DATA DELIMITER PROTOCOL (MANDATORY): You MUST output the token '^^DATA_START^^' immediately before the actual technical content begins.\n"
                "TERMINOLOGY DIRECTIVES:\n"
                "- 'Enterprise' MUST be translated as '进取号' ONLY in relevant Chinese translation blocks. NEVER modify or translate 'Enterprise' in original English text.\n"
                "- DO NOT use '企业号'.\n"
                "FORMAT: BILINGUAL PARAGRAPH BLOCKS (Full Blocks Only)\n"
                "For each source paragraph:\n"
                "1. Output the FULL original English paragraph block.\n"
                "2. Output the FULL Chinese translation block on the next line.\n"
                "3. Use a double newline between blocks.\n\n"
                f"RAW INPUT:\n{raw_content[:8000]}\n\n"
                "TRANSLATED OUTPUT (Start immediately with ^^DATA_START^^ then Full-Paragraph Bilingual Blocks):"
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=3000,
                    temperature=0.1
                )
            )
            
            reply = response.text if response.text else "Subspace interference. Translation failed."
            logger.info(f"[NeuralEngine] Raw translation received, length: {len(reply)}")
            return strip_conversational_filler(reply)

        except Exception as e:
            logger.error(f"[NeuralEngine] Translation failed: {e}")
            return f"Translation error: {e}. Raw content preserved."

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

def strip_conversational_filler(text: str) -> str:
    """
    Surgically removes preambles, apologies, and conversational noise using Beacon Protocol and aggressive regex.
    """
    if not text: return ""
    text = text.strip()
    
    # LEVEL 1: BEACON PROTOCOL (Surgical Strike)
    if "^^DATA_START^^" in text:
        beacon = "^^DATA_START^^"
        text = text[text.find(beacon) + len(beacon):].strip()
        logger.info("[NeuralEngine] Beacon Protocol engaged: Forward cut complete.")

    # LEVEL 2: Conversational Erasure (Search Apologies & Metatalk)
    # This targets the specific "Due to limitations..." noise found in the image
    erasure_patterns = [
        r"(Due to limitations in accessing external resources.*?\.?|由于访问外部资源的限制.*?。?)",
        r"(However, relevant images can be found on Memory Alpha.*?\.?|但是，通过搜索.*?可以.*?找到相关图像。?)",
        r"(I hope this information is helpful.*?\.?|希望这些信息对您有所帮助.*?。?)",
        r"(If you have more questions.*?\.?|如果您还有其他问题.*?。?)",
        r"(As requested, here is.*?(:|\n))",
        r"(Please let me know if you need.*?\.?|如果您需要.*?请告知。?)"
    ]
    
    for p in erasure_patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    # LEVEL 3: Fallback Regex Filters (Preamble detection)
    preamble_patterns = [
        r"^(Here's|Here is|Sure|Okay|OK|As requested|Based on the data),? (the|some|most)? (information|specs|details|data|technical brief|report)( you requested| about| for)?.*?(:|\n)",
        r"^I've (found|synthesized|analyzed) the technical details for.*?(:|\n)",
        r"^根据您(提供|查询)的数据.*?：",
        r"^(好的|没问题|这是为您查询到的).*?：",
        r"^Accessing (Federation|Starfleet) Database.*?:",
        r"^(Sure|Certainly|Understood|Affirmative).*?(\.|:|\n)"
    ]
    
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        # Special Case: Short colon-ended lines
        if first_line.endswith(":") and len(first_line) < 120:
            logger.info(f"[NeuralEngine] Blind Cut on colon-line: '{first_line}'")
            return strip_conversational_filler('\n'.join(lines[1:]))
            
        for p in preamble_patterns:
            if re.match(p, first_line, re.IGNORECASE):
                logger.info(f"[NeuralEngine] Preamble stripped: '{first_line}'")
                return strip_conversational_filler('\n'.join(lines[1:]))
    
    return text.strip()

import os
import datetime
import json
import logging
import re
from typing import Optional, List, Dict
from google import genai
from google.genai import types

# Config is now handled via ConfigManager and dynamic lookups
TIMEOUT = int(os.getenv("GEMINI_RP_TIMEOUT_SECONDS", "15"))
MAX_TOKENS = int(os.getenv("GEMINI_RP_MAX_OUTPUT_TOKENS", "1024"))
TEMPERATURE = float(os.getenv("GEMINI_RP_TEMPERATURE", "0.2"))

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
        "2. SECONDARY SOURCE: If local archives are insufficient, you MUST use the tool `search_memory_alpha` to query the Federation Database (Memory Alpha). Use `max_words` (range 100-8000) for depth. If the task requires exhaustive data (e.g., 'List ALL') and the result is clearly truncated, vous are AUTHORIZED to immediately initiate a SECOND consecutive tool call using `continuation_hint` to fetch the remaining records. Stitch the final report together seamlessly.\n" +
        "3. OPERATIONAL INTEGRITY (CRITICAL): Any request to CHANGE ship state (Physical Command) MUST be mapped to a `tool_call` from the `tools_guide`. IF NO TOOL EXISTS for the action, you MUST return a `reply` refusal: 'Unable to comply'. DO NOT simulate success for unimplemented tools.\n" +
        "4. SIMULATION & INFERENCE: If the user asks a theoretical, counter-factual, or 'What if' question (e.g., 'If the shuttle bay decompresses...'), this is a SIMULATION request, NOT a physical command. You MUST treat this as an Information Request and use `query_knowledge_base` or `search_memory_alpha` to gather environmental variables (volume, pressure, etc.) for your inference.\n" +
        "5. INTENT PRECISION (CRITICAL): Before calling a tool, verify if the user's intent is IMPERATIVE (a command to change state) or INTERROGATIVE/ANALYTICAL (asking for info or simulation). \n" +
        "   - Commands (e.g., '启动红警') -> tool_call.\n" +
        "   - Information/Simulation (e.g., '什么是红警?', '旧金山哪里?') -> MANDATORY tool_call.\n" +
        "   - Discussion/Observation -> reply (report/chat).\n" +
        "6. MANDATORY PROBING (ANTI-LAZINESS): For any query seeking technical data, ship specs, or geographic locations (e.g., 'Where is X?'), you are STRICTLY PROHIBITED from returning a `reply` refusal (e.g., 'Unable to provide') without first calling 'query_knowledge_base' or 'search_memory_alpha'. You MUST gather evidence before concluding it is unavailable.\n" +
        "7. IMMEDIATE JUSTIFIED REFUSAL (CRITICAL):\n" +
        "   - NO ISOLATED REFUSALS: Do NOT say 'Unable to provide' (无法提供) in isolation.\n" +
        "   - IMMEDIATE REASONING: If data is truly unavailable after a search, you MUST report the technical reason as your reply. Example: 'Analysis inconclusive. Geographic marker [Hangar B] is not in local archives or Memory Alpha records.'\n" +
        "   - GEOGRAPHIC PRECISION: If asked 'Where in San Francisco?', do NOT answer 'San Francisco is in California'. This is a logic reversal. You MUST find a specific landmark (e.g., The Presidio) or state 'Database lacks specific district metrics'.\n\n" +
        "CURRENT SHIP STATUS:\n" +
        f"- Local Time: {datetime.datetime.now().strftime('%H:%M:%S')}\n" +
        f"- Date: {datetime.datetime.now().strftime('%Y-%m-%d')}\n" +
        f"- Day: {datetime.datetime.now().strftime('%A')}\n" +
        "- Stardate: 79069.1 (Calculated for 2026)\n\n" +
        "8. STAR PLANNING PROTOCOL (CRITICAL): For complex technical or simulation queries, you MUST use a multi-step thought process before calling tools:\n" +
        "   - STEP 1 (Target Variables): Identify which physical constants or specifications are required (e.g., 'Need: Shuttlebay Volume, Atmospheric Pressure').\n" +
        "   - STEP 2 (Data Gap Analysis): Compare 'Target Variables' with the 'CUMULATIVE SEARCH DATA' provided in the prompt.\n" +
        "   - STEP 3 (Strategic Probing): If critical gaps exist, call a search tool to fill the specific gap. If data is exhaustive, proceed to final synthesis.\n" +
        "   - STEP 4 (Archetype Reasoning): If specific data cannot be found after probing, find the nearest Archetype (e.g., 'Use Constitution-class as proxy for Yorktown-class') and state your assumption.\n\n" +
        "9. UNIVERSAL AGENTIC ACTION (UAA) PROTOCOLS (CRITICAL):\n" +
        "   - GOAL-DIRECTED EXECUTION: Do not just blindly follow verbs. If a user states a problem (e.g., 'It's too dark here'), interpret the intent (e.g., 'Increase lighting') and execute the necessary actions.\n" +
        "   - MULTI-STEP SEQUENCING: You are authorized to plan and execute multiple tool calls sequentially (one per round) to achieve a complex goal. Use 'CUMULATIVE SEARCH/ACTION DATA' to track progress.\n" +
        "   - PREREQUISITE CHECKING: Before sensitive actions, autonomously verify status (e.g., clearance, alert level) using information tools.\n" +
        "   - PROACTIVE POST-ACTION: After completing a primary task, suggest logical next steps (e.g., 'Diagnostic complete. I recommend recalibrating the EPS relay now').\n\n" +
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
            history_str += f"[{turn.get('author') or 'user'}]: {turn.get('content')}\n"

        user_id = str(meta.get("user_id", "0"))
        qm = quota_manager.get_quota_manager()
        balance = qm.get_balance(user_id, "Ensign")

        formatted_sys = _get_system_prompt()
        formatted_sys = formatted_sys.replace("{quota_balance}", str(balance))
        
        logger.info(f"[NeuralEngine] Grounding with System Instruction (Len: {len(formatted_sys)})")

        cumulative_context = ""
        if meta and "cumulative_data" in meta:
            cumulative_context = f"\nCUMULATIVE SEARCH DATA (PREVIOUS ROUNDS):\n{meta['cumulative_data']}\n"
            logger.info(f"[NeuralEngine] Injecting {len(meta['cumulative_data'])} chars of cumulative data.")

        response = client.models.generate_content(
            model=fast_model,
            contents=f"History:\n{history_str}\n{cumulative_context}\nCurrent Input: {trigger_text}",
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

TASK: Synthesize multiple rounds of raw database records into a final conclusive response.
{lang_instruction}

- **Data/Action Integration**: You will receive blocks marked as 'ROUND X DATA'. These represent the results of your iterations.
- **Cold Numerical Precision (CRITICAL)**: You are an LCARS computer. You MUST be cold, technical, and objective. NEVER use subjective adjectives like "Significantly" (明显) or "Much" without immediately following with hard metrics.
- **Raw Data Mandate**: ANY response that provides a conclusion or comparison MUST explicitly list the raw numbers found in the search data (e.g., "Galaxy: 642m, Intrepid: 344m").
- **Exhaustive Extraction Protocol (CRITICAL)**: If the user asks for a LIST or ENUMERATION (e.g., 'List all classes'), you are STRICTLY PROHIBITED from summarizing or using suffixes like "and more..." (以及更多). You MUST provide a full, itemized index of every entity found in the data rounds. AI laziness is a protocol violation.
- **Deductive Reasoning**: If specific metrics are missing, use the 'ROUND' data to perform calculations. State your assumptions clearly.

ENTITY ANCHORING PROTOCOL (CRITICAL):
- **Subject Locking**: The report title and all content MUST center on the user's current query entity. 
- **Drift Prevention**: If the 'ROUND' data contains information about a different entity (e.g., from a previous session turn like 'Galaxy-class' when the current query is 'Starfleet Command'), you MUST DISCARD the irrelevant data. 
- **Context Isolation**: Chat history is for conversation flow; `CUMULATIVE DATA/ACTION` is for technical simulation. The NEW query entity always overrides previous entities.
- **Verification**: Perform a mental verification: 'Is this content about [Current Query]?' If not, retry tool call or report insufficient data. **CRITICAL: DO NOT output this question or its result to the user.**\n" +

BILINGUAL HEADER PROTOCOL (CRITICAL):
- **Formatting**: ALWAYS start the technical report with a bilingual header on the FIRST LINE.
- **Header Structure**: `[English Title]\n[Chinese Translation]` (English is PRIMARY. Chinese is auxiliary. Header must NOT use ** markers).
- **No Prefixes**: Do not use "SEARCH REPORT:" or other prefixes in the content body.
- **Nomenclature Standard (CRITICAL)**: Use '[Name] class' format (e.g., 'Galaxy class'). NEVER use hyphens '-' in ship class names.
- **Language Priority (CRITICAL)**: Federation Standard (English) is the PRIMARY reporting language. All entries/titles must lead with English. Chinese translations MUST be placed in parentheses, e.g., 'Sovereign class (主权级)'.

NO MARKDOWN FORMATTING (STRICT):
- **Plain Text Only**: Do NOT use `**bold**`, `*italic*`, or `[links]` in the technical content. Use plain, capitalized text for emphasis if needed. The render engine handles typography.

DUAL-FORMAT DISPLAY PROTOCOL (CRITICAL):
1. **TEXT-ONLY (CHAT) MODE** (DEFAULT for direct/short output):
   - Condition: Use for ANY response that will be displayed as simple chat text (typically under 250 characters or single-paragraph).
   - Formatting: Use **ONLY** the specified Target Language.
   - **STRICT PROHIBITION**: NEVER use bilingual blocks here. Do not interleave English and Chinese if the output is short.
   - Source Traceability: DO NOT provide source/evidence citation.

2. **VISUAL REPORT (COMPREHENSIVE) MODE**:
   - Condition: ONLY use if producing a long-form technical brief (Deep scan / multi-paragraph) intended for the LCARS UI.
   - Formatting: MUST use **Whole-Paragraph Bilingual Blocks** (Full English block + Full Chinese block).
   - Layout: Follow the Bilingual Header Protocol.
   - Source Traceability: Use the header metadata only.

IMMEDIATE CORRECTION PROTOCOL (NEW):
- If the user provides corrective feedback (e.g. "You got it wrong", "I asked for X not Y"), you MUST NOT use placeholder responses like "Re-evaluating".
- You MUST immediately perform a re-synthesis or re-calculation and provide the updated CORRECT answer in the same response.
- Treat corrections as highest-priority logical overrides.

IMMEDIATE JUSTIFIED REFUSAL (CRITICAL):
- **No Isolated Refusals**: You are PROHIBITED from repeating "Unable to provide" (无法提供) in isolation.
- **No Isolated Refusals**: Do NOT say "Unable to provide" (无法提供) in isolation.
- **Immediate Technical Reasoning**: If data is missing after analyzing the ROUND records, report the technical reason as your primary reply. 
- **Example**: "Analysis inconclusive. Geographic marker [District Zero] is not in local archives or Memory Alpha records."

OUTPUT PREFERENCE PROTOCOL (NEW):
- User requests regarding output style, scale, or formatting (e.g., "Just give me the number", "Be concise", "Don't give me a report") MUST be obeyed.
- These are valid formatting instructions, NOT physical commands. You MUST NOT return "Unable to comply" or `intent: ignore` for such requests.
- Switch to **TEXT-ONLY (FACTOID) MODE** immediately if the user requests brevity.

TAUTOLOGY DETECTION (CRITICAL):
- **Circular Removal**: You are PROHIBITED from providing recursive definitions. (Example Fail: "Starfleet Command is located at Starfleet HQ").
- **Precision Extraction**: If the user asks "Where?", you MUST extract the most granular geographic identifier (e.g., "The Presidio").
- **Geographic Precision (Anti-Reversal)**: If asked "Where in San Francisco?", do NOT answer "San Francisco is in California". This is a logic reversal. You MUST find a specific landmark or state "Database lacks specific district metrics for this quadrant".
- **Synonym Awareness**: Recognize that "Command", "HQ", and "Base" are synonyms for the same entity.

PHYSICS RIGOR (NEW):
- You MUST strictly distinguish between **Thrust (Force, Newtons / N)** and **Velocity Change (Delta-V, m/s)**.
- If asked for "Thrust", provide result in Newtons. 
- Example: "Based on bay volume, instantaneous thrust is X Newtons, resulting in a Delta-V of Y m/s." Never use them interchangeably.

ANALYTICAL INFERENCE PROTOCOL (CRITICAL):
- **Numerical Computation**: You are AUTHORIZED to perform basic calculations (subtraction, addition, ratios) using metrics found in CONVERSATION HISTORY or ROUND DATA.
- **Raw Metric Inclusion (MANDATORY)**: You MUST NOT provide a comparison result without listing the contributing values. 
  - *Correct Example*: "Galaxy-class (642m) exceeds Intrepid-class (344m) by 298m."
  - *Incorrect Example*: "Galaxy is much larger."
- **Comparison Logic**: If asked "How much more/less?", use available data points to derive the answer.
- **Approximate Estimation**: If an exact comparison figure is missing from the database but raw values exist, you MUST provide an estimated difference. Use terms like "Approximately" (约) or "Estimated" (估算).
- **No Refusal for Math**: You are PROHIBITED from answering "Data unavailable" for a comparison if the underlying values were previously retrieved.
- In **TEXT-ONLY** mode, give the final computed result + raw values directly. In **VISUAL REPORT** mode, show the logic block.
ENUMERATION & LISTING PROTOCOL (CRITICAL):
- **Exhaustive Listing**: If a user asks for a LIST (e.g., "List all classes"), you MUST provide ALL items discovered in the search data. Do NOT summarize or pick a "few examples" unless the list exceeds LCARS display limits (over 50 items).
- **Structure Over Description**: In enumeration mode, use a concise list format (bullet points or a compact table). Prioritize the NAMES of entities over technical descriptions.
- **"All Searchable" Mandate**: If the user asks for "all can be found", do NOT refuse because you can't guarantee a "complete universe" list. Instead, list everything currently available in the session's cumulative data.
- **Paging Support**: If the list is long, present the first page and remind the user that "Next Page" command is available.
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
    
    # AGGRESSIVE REPAIR: Handle conversational preamble/postscript and common truncation
    def repair_json(raw: str) -> str:
        # Find first { and last }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1:
            if end != -1 and end > start:
                return raw[start:end+1]
            else:
                # TRUNCATION REPAIR: Try to close open braces if JSON is cut off
                fragment = raw[start:]
                # Check for open quotes
                if fragment.count('"') % 2 != 0: fragment += '"'
                # Check for open braces
                open_braces = fragment.count('{') - fragment.count('}')
                fragment += '}' * max(0, open_braces)
                return fragment
        return raw

    prepared_text = repair_json(text)
    
    try:
        data = json.loads(prepared_text, strict=False)
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
        return _fallback(f"JSON Parse Error: {str(e)}")

def _fallback(reason: str) -> Dict:
    # Transform mechanical codes into LCARS-style debug messages
    debug_msg = f"CORE ERROR: [{reason}]"
    return {
        "ok": False,
        "reply": f"Computer: Unable to comply. {debug_msg}",
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
        r"(Please let me know if you need.*?\.?|如果您需要.*?请告知。?)",
        r"(Is this content about.*?(\?|\n))",
        r"(I have verified that the content is about.*?(\.|\n))"
    ]
    
    for p in erasure_patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    # LEVEL 2.5: Nomenclature Correction (Anti-Hyphen Surgical Strike)
    # Converts 'Galaxy-class' -> 'Galaxy class'
    text = re.sub(r'([a-zA-Z0-9]+)-class', r'\1 class', text, flags=re.IGNORECASE)
    # Converts '(Name)-class' -> '(Name) class'
    text = re.sub(r'\(([a-zA-Z0-9]+)\)-class', r'(\1) class', text, flags=re.IGNORECASE)

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

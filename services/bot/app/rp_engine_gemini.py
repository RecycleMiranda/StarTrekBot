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
from .protocol_manager import get_protocol_manager

logger = logging.getLogger(__name__)

def get_lexicon_prompt() -> str:
- Warp Field Coil -> 曲速场线圈
- Bussard Ramscoop -> 巴萨德冲压采集器
- Electro Plasma System (EPS) -> 等离子电力系统
- Impulse Propulsion System (IPS) -> 脉冲推进系统
- Cochrane -> 科克伦 (子空间畸变单位)

[Computer & Command Systems]
- LCARS -> 计算机数据库访问与读取系统
- Operations Center (Ops) -> 运作中心
- Main Bridge -> 主舰桥
- Computer Core -> 计算机核心
- Optical Data Network (ODN) -> 光学数据网络
- Isolinear Optical Chip -> 等线性光学芯片
- Isolinear rod -> 等线性数据棒
- Quad -> 夸 (Kiloquad -> 千夸 / Gigaquad -> 吉夸)
- PADD -> 个人访问显示设备

[Energy & Utilities]
- Fusion Reactor -> 聚变反应堆
- Industrial replicator -> 工业复制机
- Matter Stream -> 物质流
- Plasma power grid -> 等离子电网
- Subspace transceiver -> 子空间收发器

[Transporter Systems]
- Transporter -> 传送机 / 传送系统
- Annular Confinement Beam (ACB) -> 环形约束波束
- Pattern Buffer -> 模式缓冲器
- Heisenberg Compensator -> 海森堡补偿器

[Science & Sensors]
- Tricorder -> 三录仪
- Navigational Deflector -> 航行偏导仪

[Tactical Systems]
- Phaser -> 相位炮 / 相位器
- Photon Torpedo -> 光子鱼雷
- Quantum Torpedo -> 量子鱼雷
- Spiral-wave disruptor -> 螺旋波裂解炮 (卡达西武器)
- Polaron weapon ->极化子武器 (自治领武器)
- Defensive shield -> 防御护盾
- Shield generator -> 护盾发生器
- Self-replicating mine -> 自复制空雷

[Environmental & Crew Support]
- Life Support -> 生命保障
- Gravity Generator -> 重力发生器
- Gravity blanket -> 重力发生毯 (卡达西技术)
- Holographic Environment Simulator -> 全息环境模拟器 (全息甲板)

[Auxiliary Spacecraft & Threat Forces]
- Shuttlecraft -> 穿梭机
- Danube-class Runabout -> 多瑙河级汽艇
- Galaxy-class -> 银河级
- Sovereign-class -> 元首级
- Defiant-class -> 挑战级
- Galor-Class Attack Cruiser -> 加洛级攻击巡洋舰
- Jem'Hadar Attack Ship -> 詹哈达攻击舰
- D'Deridex-Class Warbird -> 戴克森级战鸟
- Workbee -> 工蜂
"""

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
        "DYNAMIC PROTOCOLS (TUNABLE):\n" +
        pm.get_prompt("rp_engine", "persona") + "\n" +
        pm.get_prompt("rp_engine", "chinese_style") + "\n" +
        pm.get_prompt("rp_engine", "security_protocols") + "\n" +
        pm.get_prompt("rp_engine", "tools_guide") + "\n" +
        pm.get_prompt("rp_engine", "decision_logic") + "\n\n" +
        get_lexicon_prompt()
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
        if "{quota_balance}" in formatted_sys:
            formatted_sys = formatted_sys.format(quota_balance=balance)
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

        prompt = (
            f"System: {_get_escalation_prompt().format(user_profile=user_profile_str, quota_balance=balance)}\n\n"
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

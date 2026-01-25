import os
import json
import httpx
import logging
from typing import Optional, List, Dict

from .config_manager import ConfigManager

# Config (Static env fallback for non-sensitive params)
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "3.0"))

def get_config():
    return ConfigManager.get_instance()

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "你是一个星舰级别的意图分类器。你的目标是：严格判断 [trigger] 是否在直接对“星舰计算机”下达指令或进行交互。"
    "核心规则：\n"
    "1. 即使是 follow-up 对话，如果内容明显是在和群里其他人聊天（如吐槽、闲聊、表情包），必须返回 route: 'chat'。\n"
    "2. 只有当内容是明确的‘指令’（报告、查询、计算、工具调用）或‘直接询问计算机’时，才返回 route: 'computer'。\n"
    "3. 宁可‘错杀’（不理会）也不要‘误报’（打扰群聊）。\n"
    "4. 如果确定是指令，设置 confidence >= 0.8。如果不确定或内容模棱两可，必须设为 < 0.7。\n"
    "输出必须是严格的单行 JSON：{\"route\":\"computer|chat\",\"confidence\":0.0-1.0,\"reason\":\"...\"}。"
)

async def judge_intent(trigger: Dict, context: List[Dict], meta: Optional[Dict] = None) -> Dict:
    """
    Calls Gemini to perform secondary intent classification.
    """
    config = get_config()
    api_key = config.get("gemini_api_key", "")
    model = config.get("gemini_rp_model", "gemini-2.0-flash-lite")

    if not api_key:
        raise ValueError("GEMINI_API_KEY_NOT_CONFIGURED")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    prompt = f"System: {SYSTEM_INSTRUCTION}\n\nContext: {json.dumps(context, ensure_ascii=False)}\nMeta: {json.dumps(meta or {}, ensure_ascii=False)}\nTrigger: {json.dumps(trigger, ensure_ascii=False)}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1, # Keep it deterministic
            "response_mime_type": "application/json" # Gemini supports JSON mode
        }
    }

    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        resp_json = response.json()
        
        try:
            content = resp_json["candidates"][0]["content"]["parts"][0]["text"]
            # Robust parsing
            return _parse_json_response(content)
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Failed to parse Gemini response: {resp_json}, error: {e}")
            raise ValueError("GEMINI_PARSE_ERROR")

def _parse_json_response(text: str) -> Dict:
    text = text.strip()
    # Basic strip of markdown code blocks
    if text.startswith("```"):
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
    
    try:
        data = json.loads(text)
        if "route" not in data or "confidence" not in data:
            raise ValueError("Incomplete JSON from Gemini")
        return {
            "route": data["route"],
            "confidence": float(data["confidence"]),
            "reason": data.get("reason", "gemini_judge")
        }
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON from Gemini")

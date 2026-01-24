import os
import json
import httpx
import logging
from typing import Optional, List, Dict

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "3.0"))

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "你是一个分类器，只判断 trigger 是否在对 Starship Voice Command Computer（星舰计算机）发起指令或交互。"
    "context 提供背景对话参考。"
    "输出必须是严格的单行 JSON：{\"route\":\"computer|chat\",\"confidence\":0.0-1.0,\"reason\":\"...\"}。"
    "不输出任何其他多余文字、Markdown 格式或解释。"
)

async def judge_intent(trigger: Dict, context: List[Dict], meta: Optional[Dict] = None) -> Dict:
    """
    Calls Gemini to perform secondary intent classification.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY_NOT_CONFIGURED")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
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

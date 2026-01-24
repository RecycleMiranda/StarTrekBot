import time
import re
from typing import Optional, Dict, List

# In-memory session state
# { session_id: { mode: str, expires_at: int, last_texts: list[str] } }
_session_states: Dict[str, dict] = {}

# Consts
MODE_COMPUTER = "computer"
MODE_CHAT = "chat"
DEFAULT_TTL = 30
MAX_HISTORY = 4

# Keywords and Regex
RE_MANUAL_ENTER = re.compile(r"(进入计算机模式|计算机模式|computer on|enter computer mode)", re.I)
RE_MANUAL_EXIT = re.compile(r"(退出计算机模式|退出电脑模式|computer off|exit computer mode|停止计算机)", re.I)

# Wake word: "computer" or "计算机" or "电脑" at start, followed by punctuation or space
RE_WAKE_WORD = re.compile(r"^\s*(computer|计算机|电脑)[\s,，:：]", re.I)

# Command verbs at start
COMMAND_VERBS = ["报告", "查询", "设定", "锁定", "扫描", "显示", "确认", "执行", "计算", "诊断", "导航", "同步"]

# Smalltalk signals
SMALLTALK_SIGNALS = ["哈哈", "😂", "lol", "随便聊", "讲个笑话", "你觉得", "你怎么看", "开个玩笑", "吃什么"]

def route_event(session_id: str, text: str, meta: Optional[dict] = None) -> dict:
    now = int(time.time())
    state = _session_states.get(session_id, {
        "mode": None,
        "expires_at": 0,
        "last_texts": []
    })

    # Update history
    state["last_texts"].append(text)
    state["last_texts"] = state["last_texts"][-MAX_HISTORY:]

    # Check expiration
    is_expired = now > state["expires_at"]
    if is_expired:
        state["mode"] = None

    text_clean = text.strip()
    
    # 1. Manual Commands (Highest Priority)
    if RE_MANUAL_EXIT.search(text_clean):
        state["mode"] = None
        state["expires_at"] = 0
        return _build_result(state, MODE_CHAT, 1.0, "manual_exit")
    
    if RE_MANUAL_ENTER.search(text_clean):
        state["mode"] = MODE_COMPUTER
        state["expires_at"] = now + DEFAULT_TTL
        _session_states[session_id] = state
        return _build_result(state, MODE_COMPUTER, 1.0, "manual_enter")

    # 2. Wake Word
    if RE_WAKE_WORD.match(text_clean):
        state["mode"] = MODE_COMPUTER
        state["expires_at"] = now + DEFAULT_TTL
        _session_states[session_id] = state
        return _build_result(state, MODE_COMPUTER, 0.95, "wake_word")

    # 3. Smalltalk Signal (De-escalation)
    for signal in SMALLTALK_SIGNALS:
        if signal in text_clean.lower():
            # If in computer mode, maybe exit or reduce confidence
            # For M0, if smalltalk hits, we lean towards chat
            return _build_result(state, MODE_CHAT, 0.8, "smalltalk_signal")

    # 4. Command Verbs
    for verb in COMMAND_VERBS:
        if text_clean.startswith(verb):
            state["mode"] = MODE_COMPUTER
            state["expires_at"] = now + DEFAULT_TTL
            _session_states[session_id] = state
            return _build_result(state, MODE_COMPUTER, 0.85, "command_verb")

    # 5. Mode Latch (Existing active computer mode)
    if state["mode"] == MODE_COMPUTER and not is_expired:
        state["expires_at"] = now + DEFAULT_TTL # Refresh TTL
        _session_states[session_id] = state
        return _build_result(state, MODE_COMPUTER, 0.7, "mode_latch")

    # 6. Default: Chat
    return _build_result(state, MODE_CHAT, 0.5, "default")

def _build_result(state: dict, route: str, confidence: float, reason: str) -> dict:
    return {
        "route": route,
        "confidence": confidence,
        "reason": reason,
        "mode": {
            "active": state["mode"],
            "expires_at": state["expires_at"],
            "ttl_seconds": max(0, state["expires_at"] - int(time.time()))
        }
    }

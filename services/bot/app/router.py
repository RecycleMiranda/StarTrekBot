import logging
import time
import re
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# In-memory session state
# { session_id: { mode: str, expires_at: int, last_texts: list[str] } }
_session_states: Dict[str, dict] = {}

# Consts
MODE_COMPUTER = "computer"
MODE_CHAT = "chat"
DEFAULT_TTL = 180 # Increased to 180s for better conversational persistence
MAX_HISTORY = 8  # Increased to 8 turns for deeper context
SILENCE_THRESHOLD = 1800 # 30 minutes silence before clearing history on fresh wake

# Keywords and Regex
RE_MANUAL_ENTER = re.compile(r"(进入计算机模式|计算机模式|computer on|enter computer mode)", re.I)
RE_MANUAL_EXIT = re.compile(r"(退出计算机模式|退出电脑模式|computer off|exit computer mode|停止计算机)", re.I)

# Wake word: "computer" or "计算机" or "电脑" at start
RE_WAKE_WORD = re.compile(r"^\s*(computer|计算机|电脑)", re.I)

# Command verbs at start
COMMAND_VERBS = ["报告", "查询", "设定", "锁定", "扫描", "显示", "确认", "执行", "计算", "诊断", "导航", "同步"]

# Smalltalk signals
SMALLTALK_SIGNALS = ["哈哈", "😂", "lol", "随便聊", "讲个笑话", "你觉得", "你怎么看", "开个玩笑", "吃什么"]

def get_session_context(session_id: str) -> List[Dict]:
    """
    Returns the last text entries for a session as a context list for LLM.
    """
    state = _session_states.get(session_id)
    if not state:
        return []
    return state["last_texts"]

def add_session_history(session_id: str, role: str, content: str, author: Optional[str] = None):
    """
    Manually add a turn to the session history (used for AI replies and user turns).
    """
    state = _session_states.get(session_id)
    if not state:
        return
        
    state["last_texts"].append({
        "role": role, 
        "content": content,
        "author": author or ("Computer" if role == "assistant" else "Unknown")
    })
    state["last_texts"] = state["last_texts"][-MAX_HISTORY:]

def route_event(session_id: str, text: str, meta: Optional[dict] = None) -> dict:
    now = int(time.time())
    state = _session_states.get(session_id, {
        "mode": None,
        "expires_at": 0,
        "last_activity": now,
        "last_texts": []
    })
    
    # Dynamic Activity Refresh: Update activity timestamp on every incoming event
    state["last_activity"] = now

    # Identifiers: Use Nickname/Card and include QQ ID for unique identification
    event_raw = meta.get("event_raw", {}) if meta else {}
    sender = event_raw.get("sender", {})
    user_id = str(event_raw.get("user_id", "Unknown"))
    name = sender.get("card") or sender.get("nickname") or user_id
    author = f"{name} (ID:{user_id})"

    # Update history with user turn and author attribution
    state["last_texts"].append({"role": "user", "content": text, "author": author})
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
    match = RE_WAKE_WORD.match(text_clean)
    if match:
        # Context Preservation: Only clear history if silence exceeds 30 minutes
        silence_duration = now - state.get("last_activity", 0)
        if is_expired and silence_duration > SILENCE_THRESHOLD:
            state["last_texts"] = [] # Clear history for fresh start after long silence
            logger.info(f"[Router] Stale session detected after {silence_duration}s. Resetting context.")
            
        state["mode"] = MODE_COMPUTER
        state["expires_at"] = now + DEFAULT_TTL
        state["last_activity"] = now
        _session_states[session_id] = state
        
        # Check if it's ONLY the wake word (ignoring trailing punctuation/space)
        remaining = text_clean[match.end():].strip()
        is_wake_only = not remaining or all(c in ".,，。!！?？:：" for c in remaining)
        
        result = _build_result(state, MODE_COMPUTER, 0.95, "wake_word")
        if is_wake_only:
            result["is_wake_only"] = True
        return result

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
        return _build_result(state, MODE_COMPUTER, 0.75, "mode_latch")

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

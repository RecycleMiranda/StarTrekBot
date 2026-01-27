"""
Self-Destruct Sequence Manager

Implements a Star Trek-authentic multi-step authorization flow:
1. Initialize - Creates a pending sequence
2. Authorize - Collects 3+ unique officer signatures
3. Activate - Starts the countdown

Level 12 officers can bypass the authorization step.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class DestructState(Enum):
    IDLE = "idle"
    INITIALIZED = "initialized"      # Waiting for authorization
    AUTHORIZED = "authorized"        # Ready to activate
    ACTIVE = "active"                # Countdown running
    CANCEL_PENDING = "cancel_pending"  # Cancel requested, waiting for auth
    CANCEL_AUTHORIZED = "cancel_authorized"  # Ready to confirm cancel


class DestructSequence:
    """Represents a self-destruct sequence with full state tracking."""
    
    CLE_INIT = 9
    CLE_AUTH = 8
    CLE_ACTIVATE = 9
    CLE_CANCEL = 9
    CLE_AUTH_CANCEL = 11
    
    MIN_AUTHORIZERS = 3
    AUTH_TIMEOUT_SECONDS = 300  # 5 minutes
    DEFAULT_COUNTDOWN = 300  # 5 minutes
    
    # Translation Dictionary
    MESSAGES = {
        "zh": {
            "dup_auth_init": "重复授权：发起者无法自我授权。",
            "dup_auth_id": "重复授权：该身份已记录。",
            "auth_complete": "授权码集齐，输入最终授权码后确认自毁",
            "vouch_accepted": "授权已确认：还需要 {needed} 个签名。",
            "dup_cancel_auth": "重复授权：该取消请求的身份已记录。",
            "cancel_auth_complete": "授权码集齐，输入最终授权码后确认取消自毁",
            "cancel_vouch_accepted": "取消担保已接受：还需要 {needed} 个签名以授权取消。",
            "alert_prefix": "⚠️ 自毁警报：",
            "countdown": "自毁将在 {time_str} 后执行。",
            "detonated": "启动自毁系统，解除反物质储罐约束力场，过载反应堆核心",
            "cancelled": "确认：自毁程序已取消。"
        },
        "en": {
            "dup_auth_init": "DUPLICATE AUTHORIZATION: Initiator cannot self-authorize.",
            "dup_auth_id": "DUPLICATE AUTHORIZATION: Identity already recorded.",
            "auth_complete": "AUTHORIZATION COMPLETE: {count} officers confirmed. Awaiting activation command.",
            "vouch_accepted": "AUTHORIZATION ACCEPTED: {needed} more signature(s) required.",
            "dup_cancel_auth": "DUPLICATE AUTHORIZATION: Identity already recorded for cancellation.",
            "cancel_auth_complete": "CANCELLATION AUTHORIZED: {count} officers confirmed. Awaiting confirmation.",
            "cancel_vouch_accepted": "CANCEL VOUCH ACCEPTED: {needed} more signature(s) required to authorize cancellation.",
            "alert_prefix": "⚠️ AUTO-DESTRUCT ALERT: ",
            "countdown": "Self-destruct in {time_str}.",
            "detonated": "AUTO-DESTRUCT SEQUENCE COMPLETE: REACTOR CORE BREACHED.",
            "cancelled": "Self-destruct sequence cancelled."
        }
    }

    def __init__(self, session_id: str, initiator_id: str, duration_seconds: int = 60, silent_mode: bool = False, language: str = "en"):
        self.session_id = session_id
        self.initiator_id = initiator_id
        self.duration_seconds = duration_seconds
        self.silent_mode = silent_mode
        self.language = "zh" if language and ("zh" in language.lower() or "cn" in language.lower()) else "en"
        
        self.state = DestructState.INITIALIZED
        self.authorizers: Set[str] = set()  # User IDs who authorized
        self.cancel_authorizers: Set[str] = set()  # User IDs who authorized cancel
        
        self.created_at = time.time()
        self.auth_expires_at = self.created_at + self.AUTH_TIMEOUT_SECONDS
        
        self.remaining = duration_seconds
        self.countdown_task: Optional[asyncio.Task] = None

    def _format_time(self, seconds: int) -> str:
        """Format seconds into a human-readable string (minutes and seconds)."""
        minutes = seconds // 60
        secs = seconds % 60
        
        if self.language == "zh":
            if minutes > 0:
                if secs == 0:
                    return f"{minutes}分钟"
                return f"{minutes}分{secs}秒"
            return f"{secs}秒"
        else:
            if minutes > 0:
                if secs == 0:
                    return f"{minutes}m"
                return f"{minutes}m {secs}s"
            return f"{secs}s"

    def _msg(self, key: str, **kwargs) -> str:
        """Helper to get translated message."""
        tmpl = self.MESSAGES.get(self.language, self.MESSAGES["en"]).get(key, "")
        return tmpl.format(**kwargs)

    def is_auth_expired(self) -> bool:
        return time.time() > self.auth_expires_at
    
    def add_authorizer(self, user_id: str) -> dict:
        """Add an authorizer to the sequence."""
        if user_id in self.authorizers:
            return {"ok": False, "message": self._msg("dup_auth_id")}
        
        self.authorizers.add(user_id)
        
        if len(self.authorizers) >= self.MIN_AUTHORIZERS:
            self.state = DestructState.AUTHORIZED
            return {
                "ok": True,
                "authorized": True,
                "message": self._msg("auth_complete", count=len(self.authorizers))
            }
        
        needed = self.MIN_AUTHORIZERS - len(self.authorizers)
        return {
            "ok": True,
            "authorized": False,
            "votes_needed": needed,
            "message": self._msg("vouch_accepted", needed=needed)
        }
    
    def add_cancel_authorizer(self, user_id: str) -> dict:
        """Add an authorizer to the cancel sequence."""
        if user_id in self.cancel_authorizers:
            return {"ok": False, "message": self._msg("dup_cancel_auth")}
        
        self.cancel_authorizers.add(user_id)
        
        if len(self.cancel_authorizers) >= self.MIN_AUTHORIZERS:
            self.state = DestructState.CANCEL_AUTHORIZED
            return {
                "ok": True,
                "authorized": True,
                "message": self._msg("cancel_auth_complete", count=len(self.cancel_authorizers))
            }
        
        needed = self.MIN_AUTHORIZERS - len(self.cancel_authorizers)
        return {
            "ok": True,
            "authorized": False,
            "votes_needed": needed,
            "message": self._msg("cancel_vouch_accepted", needed=needed)
        }
    
    async def run_countdown(self, notify_callback: Callable):
        """Main countdown loop."""
        try:
            while self.remaining > 0 and self.state == DestructState.ACTIVE:
                # Announcement frequency logic
                if self.remaining > 60:
                    sleep_time = 30
                elif self.remaining > 10:
                    sleep_time = 10
                else:
                    sleep_time = 1
                
                prefix = "" if self.silent_mode else self._msg("alert_prefix")
                time_str = self._format_time(self.remaining)
                msg = f"{prefix}{self._msg('countdown', time_str=time_str)}"
                
                await notify_callback(self.session_id, msg)
                
                actual_sleep = min(sleep_time, self.remaining)
                await asyncio.sleep(actual_sleep)
                self.remaining -= actual_sleep
            
            if self.state == DestructState.ACTIVE and self.remaining <= 0:
                await notify_callback(self.session_id, self._msg("detonated"))
                self.state = DestructState.IDLE
                
        except asyncio.CancelledError:
            logger.info(f"Self-destruct countdown for {self.session_id} cancelled.")


class DestructManager:
    """Singleton manager for all self-destruct sequences."""
    _instance = None
    OWNER_ID = "1993596624"  # From 1.8 script
    
    def __init__(self):
        self.sequences: Dict[str, DestructSequence] = {}
        # Track authorizations per session BEFORE initialization
        self.pending_authorizers: Dict[str, Set[str]] = {}
        # Track cancel authorizations per session BEFORE confirmation
        self.pending_cancel_authorizers: Dict[str, Set[str]] = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_sequence(self, session_id: str) -> Optional[DestructSequence]:
        session_id = str(session_id)
        seq = self.sequences.get(session_id)
        if seq and seq.is_auth_expired() and seq.state in [DestructState.INITIALIZED, DestructState.CANCEL_PENDING]:
            # Auto-expire stale auth requests
            del self.sequences[session_id]
            return None
        return seq
    
    def get_status(self, session_id: str) -> dict:
        """Returns the current status of any self-destruct sequence."""
        session_id = str(session_id)
        seq = self.get_sequence(session_id)
        
        # Determine strict language for status if possible, else default en
        lang = seq.language if seq else "en"
        msg_map = {
            "en": {
                "no_active": "No active self-destruct sequence.",
                "status_fmt": "Self-destruct sequence is in '{state}' state.",
                "remaining": " {seconds} seconds remaining.",
                "needed": " {needed} more authorizations needed."
            },
            "zh": {
                "no_active": "没有活动的自毁程序。",
                "status_fmt": "自毁程序当前处于“{state}”状态。",
                "remaining": " 剩余 {seconds} 秒。",
                "needed": " 还需要 {needed} 个授权。"
            }
        }
        msgs = msg_map.get(lang, msg_map["en"])
        
        if not seq:
            return {
                "ok": True,
                "active": False,
                "state": DestructState.IDLE.value,
                "message": msgs["no_active"]
            }
        
        authorizers_needed = max(0, DestructSequence.MIN_AUTHORIZERS - len(seq.authorizers))
        cancel_authorizers_needed = max(0, DestructSequence.MIN_AUTHORIZERS - len(seq.cancel_authorizers))
        
        status_msg = msgs["status_fmt"].format(state=seq.state.value)
        if seq.state == DestructState.ACTIVE:
            status_msg += msgs["remaining"].format(seconds=seq.remaining)
        elif seq.state == DestructState.INITIALIZED:
            status_msg += msgs["needed"].format(needed=authorizers_needed)
            
        return {
            "ok": True,
            "active": True,
            "state": seq.state.value,
            "duration_seconds": seq.duration_seconds,
            "remaining_seconds": seq.remaining if seq.state == DestructState.ACTIVE else None,
            "authorizers_count": len(seq.authorizers),
            "authorizers_needed": authorizers_needed,
            "cancel_authorizers_count": len(seq.cancel_authorizers),
            "cancel_authorizers_needed": cancel_authorizers_needed,
            "silent_mode": seq.silent_mode,
            "message": status_msg
        }

    
    async def initialize(self, session_id: str, user_id: str, clearance: int, duration: int = 300, silent: bool = False, language: str = "en", notify_callback: Callable = None) -> dict:
        """Step 1 (Version 1.8): Initialize and start countdown if authorized."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        lang_code = "zh" if language and ("zh" in language.lower() or "cn" in language.lower() or "中国" in language or "中文" in language) else "en"
        
        msgs = {
            "en": {
                "denied": "ACCESS DENIED.",
                "already_active": "SEQUENCE ALREADY ACTIVE: Current state is {state}.",
                "not_worthy": "ARE YOU WORTHY?",
                "low_clearance": "INSUFFICIENT CLEARANCE.",
                "auth_needed": "INSUFFICIENT AUTHORIZATION.",
                "success": f"AUTO-DESTRUCT ACTIVATED: {{duration_str}} countdown pending. Detonation core primed."
            },
            "zh": {
                "denied": "拒绝访问。",
                "already_active": "程序已激活：当前状态为 {state}。",
                "not_worthy": "权限不足拒绝访问",
                "low_clearance": "权限不足",
                "auth_needed": "授权人数不足 拒绝访问",
                "success": f"确认，自毁系统已启动。反应堆核心 {{duration_str}} 后破裂..."
            }
        }
        msg = msgs.get(lang_code, msgs["en"])

        # Check existing sequence
        existing = self.get_sequence(session_id)
        if existing and existing.state != DestructState.IDLE:
            return {"ok": False, "message": msg["already_active"].format(state=existing.state.value)}

        # Owner / Master bypass
        is_owner = (user_id == self.OWNER_ID)
        is_master = (clearance >= 11)
        
        if not is_owner and not is_master:
            if clearance < DestructSequence.CLE_INIT:
                return {"ok": False, "message": msg["denied"]}
                
            # Normal Level 9+ must have 3 authorizations
            auths = self.pending_authorizers.get(session_id, set())
            if len(auths) < DestructSequence.MIN_AUTHORIZERS:
                return {"ok": False, "message": msg["auth_needed"]}

        # Create and start immediately
        seq = DestructSequence(session_id, user_id, duration, silent, language=language)
        self.sequences[session_id] = seq
        
        # Start countdown immediately if authorized/bypassed
        seq.state = DestructState.ACTIVE
        if notify_callback:
            seq.countdown_task = asyncio.create_task(seq.run_countdown(notify_callback))
        
        duration_str = seq._format_time(duration)
        # Clear pending authorizers after starting
        if session_id in self.pending_authorizers:
            del self.pending_authorizers[session_id]
            
        return {
            "ok": True,
            "state": seq.state.value,
            "message": msg["success"].format(duration_str=duration_str)
        }
    
    def authorize(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 1b (Version 1.8): Store authorization before initialization."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        seq = self.get_sequence(session_id)
        lang = seq.language if seq else ("zh" if "zh" in str(session_id) else "en") # Fallback
        
        msgs = {
            "en": {
                "ineligible": f"INELIGIBLE: Clearance Level {DestructSequence.CLE_AUTH}+ required.",
                "already_active": "SEQUENCE ACTIVE: Cannot authorize during active countdown.",
                "dup": "DUPLICATE: You have already authorized.",
                "complete": "AUTHORIZATION COMPLETE: Codes collected. Awaiting final authorization to initialize.",
                "accepted": "AUTHORIZATION ACCEPTED: {needed} more signature(s) required."
            },
            "zh": {
                "ineligible": f"无权操作：需要 {DestructSequence.CLE_AUTH} 级以上权限才能授权。",
                "already_active": "无法完成：自毁系统已启动。",
                "dup": "无法完成，你已授权",
                "complete": "授权码集齐，输入最终授权码后确认自毁",
                "accepted": "接受授权 还需{needed}人授权"
            }
        }
        msg = msgs.get(lang, msgs["en"])
        
        if clearance < DestructSequence.CLE_AUTH:
            return {"ok": False, "message": msg["ineligible"]}
        
        if seq and seq.state == DestructState.ACTIVE:
            return {"ok": False, "message": msg["already_active"]}
            
        if session_id not in self.pending_authorizers:
            self.pending_authorizers[session_id] = set()
            
        auths = self.pending_authorizers[session_id]
        if user_id in auths:
            return {"ok": False, "message": msg["dup"]}
            
        auths.add(user_id)
        count = len(auths)
        
        if count >= DestructSequence.MIN_AUTHORIZERS:
            return {"ok": True, "message": msg["complete"]}
            
        needed = DestructSequence.MIN_AUTHORIZERS - count
        return {"ok": True, "message": msg["accepted"].format(needed=needed)}
    
    async def activate(self, session_id: str, user_id: str, clearance: int, notify_callback: Callable) -> dict:
        """Step 3: Activate the countdown."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        seq = self.get_sequence(session_id)
        lang = seq.language if seq else "en"
            
        msgs = {
            "en": {
                "denied": f"ACCESS DENIED: Clearance Level {DestructSequence.CLE_ACTIVATE}+ required.",
                "no_seq": "NO PENDING SEQUENCE: Initialize self-destruct first.",
                "cannot_active": "CANNOT ACTIVATE: Sequence not authorized. Current state: {state}.",
                "success": f"⚠️ AUTO-DESTRUCT ACTIVATED: Detonation in {{time_str}}. Abandon ship."
            },
            "zh": {
                "denied": f"拒绝访问：需要 {DestructSequence.CLE_ACTIVATE} 级以上权限。",
                "no_seq": "无法完成：请先初始化自毁程序。",
                "cannot_active": "无法激活：程序未授权。当前状态：{state}。",
                "success": f"⚠️ 启动自毁系统。解除反物质储罐约束力场。过载反应堆核心。警告：自毁系统已启动，{{time_str}} 后执行。"
            }
        }
        msg = msgs.get(lang, msgs["en"])
        
        if clearance < DestructSequence.CLE_ACTIVATE:
            return {"ok": False, "message": msg["denied"]}
        
        if not seq:
            return {"ok": False, "message": msg["no_seq"]}
        
        # Level 12 bypass: can activate from INITIALIZED state
        if clearance >= 12 and seq.state == DestructState.INITIALIZED:
            seq.state = DestructState.AUTHORIZED
            logger.info(f"[DestructManager] Level 12 bypass: skipping authorization for {session_id}")
        
        if seq.state != DestructState.AUTHORIZED:
            return {"ok": False, "message": msg["cannot_active"].format(state=seq.state.value)}
        
        seq.state = DestructState.ACTIVE
        seq.countdown_task = asyncio.create_task(seq.run_countdown(notify_callback))
        
        time_str = seq._format_time(seq.duration_seconds)
        return {
            "ok": True,
            "state": seq.state.value,
            "message": msg["success"].format(time_str=time_str)
        }
    
    def request_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 1 of cancel flow: Request cancellation."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        seq = self.get_sequence(session_id)
        lang = seq.language if seq else "en"
        
        msgs = {
            "en": {
                "denied": f"ACCESS DENIED: Clearance Level {DestructSequence.CLE_CANCEL}+ required.",
                "no_active": "NO ACTIVE SEQUENCE: Nothing to cancel.",
                "cancel_requested": "CANCEL REQUESTED: {needed} more senior officer signatures required to authorize cancellation."
            },
            "zh": {
                "denied": f"拒绝访问：需要 {DestructSequence.CLE_CANCEL} 级以上权限。",
                "no_active": "无活动程序：无需取消。",
                "cancel_requested": "已请求取消：还需要 {needed} 个高级军官签名以授权取消。"
            }
        }
        msg = msgs.get(lang, msgs["en"])
        
        if clearance < DestructSequence.CLE_CANCEL:
            return {"ok": False, "message": msg["denied"]}
        
        if not seq or seq.state == DestructState.IDLE:
            return {"ok": False, "message": msg["no_active"]}
        
        # Level 12 immediate cancel
        if clearance >= 12:
            return self._do_cancel(session_id, "Level 12 override")
        
        seq.state = DestructState.CANCEL_PENDING
        seq.cancel_authorizers = {user_id}  # Requester counts as first authorizer
        seq.auth_expires_at = time.time() + DestructSequence.AUTH_TIMEOUT_SECONDS
        
        needed = DestructSequence.MIN_AUTHORIZERS - 1
        return {
            "ok": True,
            "state": seq.state.value,
            "message": msg["cancel_requested"].format(needed=needed)
        }
    
    def authorize_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 1 (Version 1.8): Store cancel authorization before confirmation."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        seq = self.get_sequence(session_id)
        lang = seq.language if seq else ("zh" if "zh" in str(session_id) else "en")
        
        msgs = {
            "en": {
                "ineligible": "INSUFFICIENT CLEARANCE.",
                "no_active": "NO ACTIVE SEQUENCE.",
                "dup": "DUPLICATE: You have already authorized cancellation.",
                "complete": "CANCEL AUTHORIZATION COMPLETE: Signatures collected. Awaiting final command to terminate.",
                "accepted": "CANCEL AUTHORIZATION ACCEPTED: {needed} more senior officer signature(s) required."
            },
            "zh": {
                "ineligible": "权限不足拒绝访问",
                "no_active": "无法完成：无自毁序列运行中。",
                "dup": "无法完成，你已授权",
                "complete": "取消授权码集齐，输入终止指令后确认取消",
                "accepted": "取消担保已接受：还需要 {needed} 个高级军官签名以授权取消。"
            }
        }
        msg = msgs.get(lang, msgs["en"])
        
        if clearance < DestructSequence.CLE_AUTH_CANCEL:
            return {"ok": False, "message": msg["ineligible"]}
        
        if not seq or seq.state != DestructState.ACTIVE:
            return {"ok": False, "message": msg["no_active"]}
            
        if session_id not in self.pending_cancel_authorizers:
            self.pending_cancel_authorizers[session_id] = set()
            
        auths = self.pending_cancel_authorizers[session_id]
        if user_id in auths:
            return {"ok": False, "message": msg["dup"]}
            
        auths.add(user_id)
        count = len(auths)
        
        if count >= DestructSequence.MIN_AUTHORIZERS:
            return {"ok": True, "message": msg["complete"]}
            
        needed = DestructSequence.MIN_AUTHORIZERS - count
        return {"ok": True, "message": msg["accepted"].format(needed=needed)}
    
    def confirm_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 2 (Version 1.8): Execute the cancellation."""
        session_id = str(session_id)
        
        seq = self.get_sequence(session_id)
        lang = seq.language if seq else "en"
        
        msgs = {
            "en": {
                "denied": "INSUFFICIENT CLEARANCE.",
                "no_active": "NO ACTIVE SEQUENCE.",
                "auth_needed": "INSUFFICIENT CANCEL AUTHORIZATION."
            },
            "zh": {
                "denied": "权限不足拒绝访问",
                "no_active": "无待处理程序。",
                "auth_needed": "授权人数不足 拒绝访问"
            }
        }
        msg = msgs.get(lang.lower(), msgs["en"])
        
        if clearance < DestructSequence.CLE_CANCEL:
            return {"ok": False, "message": msg["denied"]}
            
        if not seq or seq.state != DestructState.ACTIVE:
            return {"ok": False, "message": msg["no_active"]}
            
        # Check authorizations
        auths = self.pending_cancel_authorizers.get(session_id, set())
        
        # Masters / Owners bypass
        is_owner = (user_id == self.OWNER_ID)
        is_master = (clearance >= 11)
        
        if not is_owner and not is_master and len(auths) < DestructSequence.MIN_AUTHORIZERS:
            return {"ok": False, "message": msg["auth_needed"]}
            
        # Execute cancel
        result = self._do_cancel(session_id, "授权终止")
        
        # Clear signatures
        if session_id in self.pending_cancel_authorizers:
            del self.pending_cancel_authorizers[session_id]
            
        return result
    
    def _do_cancel(self, session_id: str, reason: str) -> dict:
        """Actually cancel the sequence."""
        seq = self.sequences.get(session_id)
        lang = seq.language if seq else "en"
        
        msgs = {
            "en": "✅ AUTO-DESTRUCT ABORTED: {reason}. Ship systems returning to nominal status.",
            "zh": "✅ 自毁程序已终止：{reason}。舰船系统恢复正常。"
        }
        
        if seq:
            if seq.countdown_task:
                seq.countdown_task.cancel()
            del self.sequences[session_id]
        
        return {
            "ok": True,
            "state": DestructState.IDLE.value,
            "message": msgs.get(lang, msgs["en"]).format(reason=reason)
        }


def get_destruct_manager():
    return DestructManager.get_instance()

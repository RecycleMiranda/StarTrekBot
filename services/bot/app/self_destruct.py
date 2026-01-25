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
    
    MIN_CLEARANCE = 9
    MIN_AUTHORIZERS = 3
    AUTH_TIMEOUT_SECONDS = 300  # 5 minutes
    DEFAULT_COUNTDOWN = 60
    
    def __init__(self, session_id: str, initiator_id: str, duration_seconds: int = 60, silent_mode: bool = False):
        self.session_id = session_id
        self.initiator_id = initiator_id
        self.duration_seconds = duration_seconds
        self.silent_mode = silent_mode
        
        self.state = DestructState.INITIALIZED
        self.authorizers: Set[str] = set()  # User IDs who authorized
        self.cancel_authorizers: Set[str] = set()  # User IDs who authorized cancel
        
        self.created_at = time.time()
        self.auth_expires_at = self.created_at + self.AUTH_TIMEOUT_SECONDS
        
        # Countdown state
        self.remaining = duration_seconds
        self.countdown_task: Optional[asyncio.Task] = None
    
    def is_auth_expired(self) -> bool:
        return time.time() > self.auth_expires_at
    
    def add_authorizer(self, user_id: str) -> dict:
        """Add an authorizer to the sequence."""
        if user_id == self.initiator_id:
            return {"ok": False, "message": "DUPLICATE AUTHORIZATION: Initiator cannot self-authorize."}
        
        if user_id in self.authorizers:
            return {"ok": False, "message": "DUPLICATE AUTHORIZATION: Identity already recorded."}
        
        self.authorizers.add(user_id)
        
        if len(self.authorizers) >= self.MIN_AUTHORIZERS:
            self.state = DestructState.AUTHORIZED
            return {
                "ok": True,
                "authorized": True,
                "message": f"AUTHORIZATION COMPLETE: {len(self.authorizers)} officers confirmed. Awaiting activation command."
            }
        
        needed = self.MIN_AUTHORIZERS - len(self.authorizers)
        return {
            "ok": True,
            "authorized": False,
            "votes_needed": needed,
            "message": f"VOUCH ACCEPTED: {needed} more signature(s) required."
        }
    
    def add_cancel_authorizer(self, user_id: str) -> dict:
        """Add an authorizer to the cancel sequence."""
        if user_id in self.cancel_authorizers:
            return {"ok": False, "message": "DUPLICATE AUTHORIZATION: Identity already recorded for cancellation."}
        
        self.cancel_authorizers.add(user_id)
        
        if len(self.cancel_authorizers) >= self.MIN_AUTHORIZERS:
            self.state = DestructState.CANCEL_AUTHORIZED
            return {
                "ok": True,
                "authorized": True,
                "message": f"CANCELLATION AUTHORIZED: {len(self.cancel_authorizers)} officers confirmed. Awaiting confirmation."
            }
        
        needed = self.MIN_AUTHORIZERS - len(self.cancel_authorizers)
        return {
            "ok": True,
            "authorized": False,
            "votes_needed": needed,
            "message": f"CANCEL VOUCH ACCEPTED: {needed} more signature(s) required to authorize cancellation."
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
                
                prefix = "" if self.silent_mode else "⚠️ AUTO-DESTRUCT ALERT: "
                msg = f"{prefix}Self-destruct in {self.remaining} seconds."
                
                await notify_callback(self.session_id, msg)
                
                actual_sleep = min(sleep_time, self.remaining)
                await asyncio.sleep(actual_sleep)
                self.remaining -= actual_sleep
            
            if self.state == DestructState.ACTIVE and self.remaining <= 0:
                await notify_callback(self.session_id, "💥 AUTO-DESTRUCT SEQUENCE COMPLETE. SHIP HAS BEEN DESTROYED.")
                self.state = DestructState.IDLE
                
        except asyncio.CancelledError:
            logger.info(f"Self-destruct countdown for {self.session_id} cancelled.")


class DestructManager:
    """Singleton manager for all self-destruct sequences."""
    _instance = None
    
    def __init__(self):
        self.sequences: Dict[str, DestructSequence] = {}
    
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
        
        if not seq:
            return {
                "ok": True,
                "active": False,
                "state": DestructState.IDLE.value,
                "message": "No active self-destruct sequence."
            }
        
        authorizers_needed = max(0, DestructSequence.MIN_AUTHORIZERS - len(seq.authorizers))
        cancel_authorizers_needed = max(0, DestructSequence.MIN_AUTHORIZERS - len(seq.cancel_authorizers))
        
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
            "message": f"Self-destruct sequence is in '{seq.state.value}' state." + 
                       (f" {seq.remaining} seconds remaining." if seq.state == DestructState.ACTIVE else "") +
                       (f" {authorizers_needed} more authorizations needed." if seq.state == DestructState.INITIALIZED else "")
        }

    
    def initialize(self, session_id: str, user_id: str, clearance: int, duration: int = 60, silent: bool = False) -> dict:
        """Step 1: Initialize the self-destruct sequence."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"ACCESS DENIED: Minimum Clearance Level {DestructSequence.MIN_CLEARANCE} required. Current: {clearance}."}
        
        existing = self.get_sequence(session_id)
        if existing and existing.state != DestructState.IDLE:
            return {"ok": False, "message": f"SEQUENCE ALREADY ACTIVE: Current state is {existing.state.value}."}
        
        seq = DestructSequence(session_id, user_id, duration, silent)
        self.sequences[session_id] = seq
        
        return {
            "ok": True,
            "state": seq.state.value,
            "message": f"AUTO-DESTRUCT INITIALIZED: {duration} second countdown pending. Awaiting authorization from {DestructSequence.MIN_AUTHORIZERS} senior officers."
        }
    
    def authorize(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 2: Add authorization signature."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"INELIGIBLE: Clearance Level {DestructSequence.MIN_CLEARANCE}+ required to authorize."}
        
        seq = self.get_sequence(session_id)
        if not seq:
            return {"ok": False, "message": "NO PENDING SEQUENCE: Initialize self-destruct first."}
        
        if seq.state != DestructState.INITIALIZED:
            return {"ok": False, "message": f"INVALID STATE: Sequence is in '{seq.state.value}' state, not awaiting authorization."}
        
        return seq.add_authorizer(user_id)
    
    async def activate(self, session_id: str, user_id: str, clearance: int, notify_callback: Callable) -> dict:
        """Step 3: Activate the countdown."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"ACCESS DENIED: Clearance Level {DestructSequence.MIN_CLEARANCE}+ required."}
        
        seq = self.get_sequence(session_id)
        if not seq:
            return {"ok": False, "message": "NO PENDING SEQUENCE: Initialize self-destruct first."}
        
        # Level 12 bypass: can activate from INITIALIZED state
        if clearance >= 12 and seq.state == DestructState.INITIALIZED:
            seq.state = DestructState.AUTHORIZED
            logger.info(f"[DestructManager] Level 12 bypass: skipping authorization for {session_id}")
        
        if seq.state != DestructState.AUTHORIZED:
            return {"ok": False, "message": f"CANNOT ACTIVATE: Sequence is in '{seq.state.value}' state. Authorization required."}
        
        seq.state = DestructState.ACTIVE
        seq.countdown_task = asyncio.create_task(seq.run_countdown(notify_callback))
        
        return {
            "ok": True,
            "state": seq.state.value,
            "message": f"⚠️ AUTO-DESTRUCT ACTIVATED: {seq.duration_seconds} seconds to detonation. This ship will self-destruct."
        }
    
    def request_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 1 of cancel flow: Request cancellation."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"ACCESS DENIED: Clearance Level {DestructSequence.MIN_CLEARANCE}+ required."}
        
        seq = self.get_sequence(session_id)
        if not seq or seq.state == DestructState.IDLE:
            return {"ok": False, "message": "NO ACTIVE SEQUENCE: Nothing to cancel."}
        
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
            "message": f"CANCEL REQUESTED: {needed} more senior officer signatures required to authorize cancellation."
        }
    
    def authorize_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 2 of cancel flow: Add cancel authorization."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"INELIGIBLE: Clearance Level {DestructSequence.MIN_CLEARANCE}+ required."}
        
        seq = self.get_sequence(session_id)
        if not seq:
            return {"ok": False, "message": "NO PENDING SEQUENCE."}
        
        if seq.state != DestructState.CANCEL_PENDING:
            return {"ok": False, "message": f"INVALID STATE: Sequence is '{seq.state.value}', not awaiting cancel authorization."}
        
        return seq.add_cancel_authorizer(user_id)
    
    def confirm_cancel(self, session_id: str, user_id: str, clearance: int) -> dict:
        """Step 3 of cancel flow: Confirm and execute cancellation."""
        session_id = str(session_id)
        
        if clearance < DestructSequence.MIN_CLEARANCE:
            return {"ok": False, "message": f"ACCESS DENIED: Clearance Level {DestructSequence.MIN_CLEARANCE}+ required."}
        
        seq = self.get_sequence(session_id)
        if not seq:
            return {"ok": False, "message": "NO PENDING SEQUENCE."}
        
        # Level 12 can confirm from CANCEL_PENDING
        if clearance >= 12 and seq.state == DestructState.CANCEL_PENDING:
            return self._do_cancel(session_id, "Level 12 override")
        
        if seq.state != DestructState.CANCEL_AUTHORIZED:
            return {"ok": False, "message": f"CANNOT CONFIRM: Cancel not yet authorized. Current state: '{seq.state.value}'."}
        
        return self._do_cancel(session_id, "Multi-signature authorization")
    
    def _do_cancel(self, session_id: str, reason: str) -> dict:
        """Actually cancel the sequence."""
        seq = self.sequences.get(session_id)
        if seq:
            if seq.countdown_task:
                seq.countdown_task.cancel()
            del self.sequences[session_id]
        
        return {
            "ok": True,
            "state": DestructState.IDLE.value,
            "message": f"✅ AUTO-DESTRUCT ABORTED: {reason}. Ship systems returning to nominal status."
        }


def get_destruct_manager():
    return DestructManager.get_instance()

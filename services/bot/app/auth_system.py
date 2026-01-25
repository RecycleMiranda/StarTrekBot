import time
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class AuthAction:
    def __init__(self, action_id: str, initiator_id: str, required_votes: int, metadata: dict):
        self.action_id = action_id
        self.initiator_id = initiator_id
        self.required_votes = required_votes
        self.metadata = metadata
        self.votes: Set[str] = {initiator_id}
        self.created_at = time.time()
        self.expires_at = self.created_at + 300 # 5 minute window for auth

    def is_complete(self) -> bool:
        return len(self.votes) >= self.required_votes

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class UniversalAuthSystem:
    _instance = None
    
    def __init__(self):
        # session_id -> { action_type -> AuthAction }
        self.pending_actions: Dict[str, Dict[str, AuthAction]] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def request_action(self, session_id: str, action_type: str, user_id: str, clearance: int, metadata: dict) -> dict:
        """Starts an authorization request."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        # Rule: Level 12 can act alone
        if clearance >= 12:
            return {"ok": True, "authorized": True, "message": "COMMAND AUTHORIZED: Solo override active."}
            
        # Rule: Level 9-11 requires 3 people
        if clearance < 9:
            return {"ok": False, "message": f"ACCESS DENIED: Minimum Clearance Level 9 required for multi-sig authorization. Current: {clearance}."}
            
        if session_id not in self.pending_actions:
            self.pending_actions[session_id] = {}
            
        action = AuthAction(action_type, user_id, required_votes=3, metadata=metadata)
        self.pending_actions[session_id][action_type] = action
        
        return {
            "ok": True, 
            "authorized": False, 
            "votes_needed": 2, 
            "message": f"AUTHORIZATION PENDING: {action_type} requires 2 additional senior officer signatures."
        }

    def vouch_for_action(self, session_id: str, action_type: str, user_id: str, clearance: int) -> dict:
        """Adds a signature to a pending action."""
        session_id = str(session_id)
        user_id = str(user_id)
        
        if session_id not in self.pending_actions or action_type not in self.pending_actions[session_id]:
            return {"ok": False, "message": f"No pending {action_type} sequence found in this sector."}
            
        action = self.pending_actions[session_id][action_type]
        
        if action.is_expired():
            del self.pending_actions[session_id][action_type]
            return {"ok": False, "message": "AUTHORIZATION EXPIRED: Sequence reset required."}
            
        if clearance < 9:
            return {"ok": False, "message": "Ineligible for authorization. Minimum Clearance Level 9 required."}
            
        if user_id in action.votes:
            return {"ok": False, "message": "DUPLICATE AUTHORIZATION: Identity already recorded."}
            
        action.votes.add(user_id)
        
        if action.is_complete():
            metadata = action.metadata
            del self.pending_actions[session_id][action_type]
            return {"ok": True, "authorized": True, "metadata": metadata, "message": f"AUTHORIZATION COMPLETE: Running sequence {action_type}."}
            
        needed = action.required_votes - len(action.votes)
        return {
            "ok": True, 
            "authorized": False, 
            "votes_needed": needed, 
            "message": f"VOUCH ACCEPTED: {needed} more signature(s) required for {action_type}."
        }

    def cancel_request(self, session_id: str, action_type: str, clearance: int) -> dict:
        """Cancels a pending request (requires Level 9+)."""
        session_id = str(session_id)
        if clearance < 9:
             return {"ok": False, "message": "ACCESS DENIED: Insufficient clearance to abort auth sequence."}
             
        if session_id in self.pending_actions and action_type in self.pending_actions[session_id]:
            del self.pending_actions[session_id][action_type]
            return {"ok": True, "message": f"Sequence {action_type} aborted."}
        return {"ok": False, "message": "No active sequence found."}

def get_auth_system():
    return UniversalAuthSystem.get_instance()

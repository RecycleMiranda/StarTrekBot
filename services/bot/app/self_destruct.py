import asyncio
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SelfDestructSequence:
    def __init__(self, session_id: str, duration_seconds: int, silent_mode: bool = False):
        self.session_id = session_id
        self.remaining = duration_seconds
        self.silent_mode = silent_mode
        self.is_active = True
        self.task: Optional[asyncio.Task] = None

    async def run(self, notify_callback):
        """Main countdown loop."""
        try:
            while self.remaining > 0 and self.is_active:
                # Announcement Frequency Logic
                if self.remaining > 60:
                    sleep_time = 30
                elif self.remaining > 10:
                    sleep_time = 10
                else:
                    sleep_time = 1
                
                # Format message
                prefix = "" if self.silent_mode else "⚠️ AUTO-DESTRUCT ALERT: "
                msg = f"{prefix}Self-destruct in {self.remaining} seconds."
                
                # Notify (this would go back to the chat platform)
                await notify_callback(self.session_id, msg)
                
                # Wait for interval or 1s (to react faster to changes)
                # But actual_sleep should be at least 1
                actual_sleep = min(sleep_time, self.remaining)
                await asyncio.sleep(actual_sleep)
                self.remaining -= actual_sleep
            
            if self.is_active and self.remaining <= 0:
                await notify_callback(self.session_id, "💥 AUTO-DESTRUCT SEQUENCE COMPLETE. SHIP HAS BEEN DESTROYED.")
                # Sequence terminates
                
        except asyncio.CancelledError:
            self.is_active = False
            logger.info(f"Self-destruct sequence for {self.session_id} cancelled.")

class DestructManager:
    _instance = None
    
    def __init__(self):
        # session_id -> SelfDestructSequence
        self.active_sequences: Dict[str, SelfDestructSequence] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_sequence(self, session_id: str, duration: int, silent: bool, notify_callback):
        """Initiates the destruct sequence."""
        session_id = str(session_id)
        if session_id in self.active_sequences:
            return {"ok": False, "message": "Sequence already active in this sector."}
            
        seq = SelfDestructSequence(session_id, duration, silent)
        self.active_sequences[session_id] = seq
        seq.task = asyncio.create_task(seq.run(notify_callback))
        
        return {"ok": True, "message": f"AUTO-DESTRUCT INITIATED: {duration} seconds remain."}

    async def abort_sequence(self, session_id: str):
        """Cancels an active sequence."""
        session_id = str(session_id)
        if session_id not in self.active_sequences:
            return {"ok": False, "message": "No active destruct sequence detected."}
            
        seq = self.active_sequences[session_id]
        if seq.task:
            seq.task.cancel()
            
        del self.active_sequences[session_id]
        return {"ok": True, "message": "AUTO-DESTRUCT ABORTED. Ship systems returning to nominal status."}

def get_destruct_manager():
    return DestructManager.get_instance()

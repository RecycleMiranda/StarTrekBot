import os
import time
import asyncio
import logging
import uuid
from collections import deque
from typing import Dict, Optional, List
from . import moderation
from . import sender_mock

# Config from Env
ENABLED = os.getenv("SENDQ_ENABLED", "true").lower() == "true"
GLOBAL_RPS = float(os.getenv("SENDQ_GLOBAL_RPS", "2.0"))
SESSION_COOLDOWN_MS = int(os.getenv("SENDQ_SESSION_COOLDOWN_MS", "1200"))
MAX_QUEUE_PER_SESSION = int(os.getenv("SENDQ_MAX_QUEUE_PER_SESSION", "30"))
TICK_MS = int(os.getenv("SENDQ_WORKER_TICK_MS", "100"))

logger = logging.getLogger(__name__)

class SendItem:
    def __init__(self, session_key: str, text: str, meta: dict):
        self.id = str(uuid.uuid4())
        self.session_key = session_key
        self.text = text
        self.meta = meta
        self.created_at = time.time()

class SendQueue:
    _instance: Optional['SendQueue'] = None

    def __init__(self):
        self.queues: Dict[str, deque] = {}
        self.last_sent_at: Dict[str, float] = {}
        self.global_last_sent_at = 0.0
        self.stop_event = asyncio.Event()
        self.lock = asyncio.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def enqueue_send(self, session_key: str, text: str, meta: dict) -> dict:
        async with self.lock:
            if session_key not in self.queues:
                self.queues[session_key] = deque()
            
            queue = self.queues[session_key]
            if len(queue) >= MAX_QUEUE_PER_SESSION:
                logger.warning(f"Queue full for session {session_key}, dropping message")
                return {"error": "queue_full", "session_key": session_key}
            
            item = SendItem(session_key, text, meta)
            queue.append(item)
            return {
                "id": item.id,
                "session_key": session_key,
                "queue_len": len(queue)
            }

    def get_status(self) -> dict:
        return {
            "total_queued": sum(len(q) for q in self.queues.values()),
            "session_count": len(self.queues),
            "sessions": {k: len(v) for k, v in list(self.queues.items())[:20]},
            "global_rps_limit": GLOBAL_RPS,
            "session_cooldown_ms": SESSION_COOLDOWN_MS
        }

    async def worker_loop(self):
        logger.info("SendQueue worker started")
        global_interval = 1.0 / GLOBAL_RPS
        
        while not self.stop_event.is_set():
            now = time.time()
            item_to_send = None

            async with self.lock:
                # Simple round-robin: iterate through sessions
                # Note: dict order is insertion order in modern Python
                for session_key, queue in list(self.queues.items()):
                    if not queue:
                        continue
                    
                    # Check session cooldown
                    last_sent = self.last_sent_at.get(session_key, 0.0)
                    if (now - last_sent) * 1000 < SESSION_COOLDOWN_MS:
                        continue
                        
                    # Check global rate limit
                    if (now - self.global_last_sent_at) < global_interval:
                        continue
                    
                    # Conditions met, take item
                    item_to_send = queue.popleft()
                    self.last_sent_at[session_key] = now
                    self.global_last_sent_at = now
                    break
            
            if item_to_send:
                await self._process_send(item_to_send)
            else:
                await asyncio.sleep(TICK_MS / 1000.0)

    async def _process_send(self, item: SendItem):
        text_to_send = item.text
        
        # Output Moderation
        mod_res = await moderation.moderate_text(text_to_send, "output", item.meta)
        mod_info = {
            "allow": mod_res["allow"],
            "action": mod_res["action"],
            "reason": mod_res["reason"],
            "provider": mod_res["provider"]
        }
        
        if not mod_res["allow"]:
            logger.warning(f"Message blocked by output moderation: {item.id}")
            text_to_send = "Computer: Unable to comply."
            mod_info["blocked"] = True
        
        # Actual "send" (Mock)
        # Note: meta already includes session_key, group_id etc.
        await sender_mock.send(text_to_send, item.meta, item.id, mod_info)

    def stop(self):
        self.stop_event.set()

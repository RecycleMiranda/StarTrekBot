import os
import time
import asyncio
import logging
import uuid
import json
from collections import deque
from typing import Dict, Optional, List
from . import moderation
from .sender_base import Sender

# Config from Env
ENABLED = os.getenv("SENDQ_ENABLED", "true").lower() == "true"
GLOBAL_RPS = float(os.getenv("SENDQ_GLOBAL_RPS", "2.0"))
SESSION_COOLDOWN_MS = int(os.getenv("SENDQ_SESSION_COOLDOWN_MS", "1200"))
MAX_QUEUE_PER_SESSION = int(os.getenv("SENDQ_MAX_QUEUE_PER_SESSION", "30"))
TICK_MS = int(os.getenv("SENDQ_WORKER_TICK_MS", "100"))

logger = logging.getLogger(__name__)

class SendItem:
    def __init__(self, session_key: str, text: str, meta: dict, priority: int = 3):
        self.id = str(uuid.uuid4())
        self.session_key = session_key
        self.text = text
        self.meta = meta
        self.priority = priority # 1: ALPHA, 2: BETA, 3: GAMMA
        self.created_at = time.time()

class SendQueue:
    _instance: Optional['SendQueue'] = None

    def __init__(self, sender: Sender):
        self.sender = sender
        self.queues: Dict[str, deque] = {}
        self.last_sent_at: Dict[str, float] = {}
        self.global_last_sent_at = 0.0
        self.stop_event = asyncio.Event()
        self.lock = asyncio.Lock()

    @classmethod
    def get_instance(cls, sender: Optional[Sender] = None):
        if cls._instance is None:
            if sender is None:
                raise ValueError("Sender must be provided for the first call to get_instance")
            cls._instance = cls(sender)
        return cls._instance

    async def enqueue_send(self, session_key: str, text: str, meta: dict, priority: int = 3) -> dict:
        async with self.lock:
            if session_key not in self.queues:
                self.queues[session_key] = deque()
            
            queue = self.queues[session_key]
            if len(queue) >= MAX_QUEUE_PER_SESSION:
                logger.warning(f"Queue full for session {session_key}, dropping message")
                return {"error": "queue_full", "session_key": session_key}
            
            item = SendItem(session_key, text, meta, priority=priority)
            
            # Insert based on priority (Surgical placement)
            if priority < 3:
                # Find the first index where priority is higher and insert before it
                inserted = False
                for i in range(len(queue)):
                    if queue[i].priority > priority:
                        queue.insert(i, item)
                        inserted = True
                        break
                if not inserted:
                    queue.append(item)
            else:
                queue.append(item)
                
            return {
                "id": item.id,
                "session_key": session_key,
                "priority": priority,
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
        logger.info("SendQueue worker started with Priority Awareness (1: ALPHA, 2: BETA, 3: GAMMA)")
        global_interval = 1.0 / GLOBAL_RPS
        
        while not self.stop_event.is_set():
            now = time.time()
            item_to_send = None

            async with self.lock:
                # 1. SCAN FOR ALPHA (Priority 1) across ALL sessions first
                for session_key, queue in list(self.queues.items()):
                    if queue and queue[0].priority == 1:
                        # Check global rate limit only (ALPHA bypasses session cooldown if critical?)
                        # Actually keep session cooldown to prevent flood but prioritize ALPHA
                        if (now - self.global_last_sent_at) >= global_interval:
                            item_to_send = queue.popleft()
                            self.last_sent_at[session_key] = now
                            self.global_last_sent_at = now
                            break
                
                if not item_to_send:
                    # 2. STANDARD ROUND-ROBIN for BETA/GAMMA
                    for session_key, queue in list(self.queues.items()):
                        if not queue: continue
                        
                        last_sent = self.last_sent_at.get(session_key, 0.0)
                        if (now - last_sent) * 1000 < SESSION_COOLDOWN_MS: continue
                        if (now - self.global_last_sent_at) < global_interval: continue
                        
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
            "allow": mod_res.get("allow", True),
            "action": mod_res.get("action", "none"),
            "reason": mod_res.get("reason", ""),
            "provider": mod_res.get("provider", "none")
        }
        
        if not mod_res.get("allow", True):
            logger.warning(f"Message blocked by output moderation: {item.id}")
            text_to_send = "Computer: Unable to comply."
            mod_info["blocked"] = True
        
        # Actual "send" via injected sender with error logging
        try:
            await self.sender.send(text_to_send, item.meta, item.id, mod_info)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send message {item.id} via {type(self.sender).__name__}: {error_msg}")
            
            # Log error to send_log.jsonl (using a side-effect log)
            from .sender_mock import SEND_LOG_PATH, DATA_DIR
            error_entry = {
                "ts": int(time.time()),
                "send_item_id": item.id,
                "session_key": item.session_key,
                "error": error_msg,
                "provider": type(self.sender).__name__,
                "status": "failed"
            }
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(SEND_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(error_entry, ensure_ascii=False) + "\n")
            except Exception as le:
                logger.warning(f"Failed to write error log: {le}")

    def stop(self):
        self.stop_event.set()

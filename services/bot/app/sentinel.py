import asyncio
import time
import logging
import json
import os
import uuid
import re
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class SentinelTrigger:
    id: str
    condition_code: str  # Python snippet returning bool
    action_code: str     # Python snippet executing action
    description: str
    creator_id: str
    created_at: float
    ttl: float          # Time to live in seconds, -1 for permanent
    is_active: bool = True
    hit_count: int = 0
    last_run: float = 0
    tags: List[str] = None

class SentinelRegistry:
    _instance = None
    
    def __init__(self):
        self.triggers: Dict[str, SentinelTrigger] = {}
        self.storage_path = os.path.join(os.path.dirname(__file__), "autonomous_storage")
        os.makedirs(self.storage_path, exist_ok=True)
        self._load_permanent_triggers()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_trigger(self, condition: str, action: str, desc: str, user_id: str, ttl: float = 3600) -> str:
        tid = f"TRI-{uuid.uuid4().hex[:6].upper()}"
        trigger = SentinelTrigger(
            id=tid,
            condition_code=condition,
            action_code=action,
            description=desc,
            creator_id=user_id,
            created_at=time.time(),
            ttl=ttl,
            tags=[]
        )
        self.triggers[tid] = trigger
        
        if ttl == -1: # Permanent logic
            self._save_trigger(trigger)
            
        logger.info(f"[Sentinel] New trigger registered: {tid} - {desc}")
        return tid

    def _save_trigger(self, trigger: SentinelTrigger):
        filepath = os.path.join(self.storage_path, f"{trigger.id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(trigger), f, indent=2)

    def _load_permanent_triggers(self):
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.storage_path, filename), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        trigger = SentinelTrigger(**data)
                        self.triggers[trigger.id] = trigger
                except Exception as e:
                    logger.error(f"Failed to load trigger {filename}: {e}")

    def get_active_triggers(self) -> List[SentinelTrigger]:
        now = time.time()
        active = []
        to_delete = []
        
        for tid, t in self.triggers.items():
            if t.ttl != -1 and (now - t.created_at) > t.ttl:
                to_delete.append(tid)
                continue
            if t.is_active:
                active.append(t)
                
        for tid in to_delete:
            del self.triggers[tid]
            
        return active

class SentinelExecutionEngine:
    def __init__(self, ship_systems):
        self.ss = ship_systems

    def _create_sandbox(self) -> Dict[str, Any]:
        """Provides a safe subset of global functions and ship systems."""
        return {
            "ship": self.ss,
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "len": len,
            "re": re,
            "time": time.time
        }

    async def evaluate_and_execute(self):
        registry = SentinelRegistry.get_instance()
        triggers = registry.get_active_triggers()
        
        if not triggers:
            return

        sandbox = self._create_sandbox()
        
        for t in triggers:
            try:
                # 1. Evaluate Condition
                # We use a very strict check since this is AI generated
                condition_result = eval(t.condition_code, {"__builtins__": {}}, sandbox)
                
                if condition_result:
                    logger.info(f"[Sentinel] Trigger FIRED: {t.id} ({t.description})")
                    # 2. Execute Action
                    # exec is used for multi-line action logic
                    exec(t.action_code, {"__builtins__": {}}, sandbox)
                    
                    t.hit_count += 1
                    t.last_run = time.time()
                    
                    # If single-shot (like a specific request), deactivate
                    if "oneshot" in (t.tags or []):
                        t.is_active = False
                        
            except Exception as e:
                logger.error(f"[Sentinel] Error in trigger {t.id}: {e}")
                t.is_active = False # Disable faulty scripts

async def sentinel_loop(ship_systems, interval=2.0):
    """Background loop to periodically check triggers."""
    engine = SentinelExecutionEngine(ship_systems)
    while True:
        try:
            await engine.evaluate_and_execute()
        except Exception as e:
            logger.error(f"Sentinel Loop Error: {e}")
        await asyncio.sleep(interval)

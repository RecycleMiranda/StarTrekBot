import asyncio
import json
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "config", "procedures_registry.json")

class ProcedureEngine:
    """
    ADS 6.0: Procedural Execution Engine.
    Executes timed sequences of actions defined in the registry.
    """
    _instance = None
    _active_tasks: Dict[str, asyncio.Task] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProcedureEngine, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_registry(self) -> Dict:
        try:
            if os.path.exists(REGISTRY_PATH):
                with open(REGISTRY_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[ProcedureEngine] Failed to load registry: {e}")
        return {}

    async def execute_protocol(self, protocol_id: str, session_id: str) -> Dict:
        """Starts a protocol execution in the background."""
        registry = self._load_registry()
        # Search for protocol across categories
        protocol = None
        for cat in registry.values():
            if protocol_id in cat:
                protocol = cat[protocol_id]
                break
        
        if not protocol:
            return {"ok": False, "message": f"Protocol '{protocol_id}' not found."}

        # 1. Pre-conditions Check
        from .ship_systems import get_ship_systems
        ss = get_ship_systems()
        for sys_name, req_state in protocol.get("pre_conditions", {}).items():
            comp = ss.get_component(sys_name)
            if not comp or comp.get("current_state") != req_state:
                return {"ok": False, "message": f"Pre-condition failed: {sys_name} must be {req_state}."}

        # 2. Schedule Execution
        task_id = f"{session_id}_{protocol_id}"
        if task_id in self._active_tasks and not self._active_tasks[task_id].done():
            return {"ok": False, "message": f"Protocol '{protocol_id}' is already running in this session."}

        task = asyncio.create_task(self._run_steps(protocol, session_id))
        self._active_tasks[task_id] = task
        
        return {"ok": True, "message": f"Initiating {protocol['name']}... Procedure is running in background."}

    async def _run_steps(self, protocol: Dict, session_id: str):
        from .ship_systems import accept_action
        from .signal_hub import get_signal_hub
        hub = get_signal_hub()
        
        logger.info(f"[ProcedureEngine] Starting {protocol['name']}")
        
        for step in protocol.get("steps", []):
            delay = step.get("delay", 0)
            if delay > 0:
                await asyncio.sleep(delay)
            
            action = step.get("action")
            system = step.get("system")
            params = step.get("params", {})
            
            if action == "BROADCAST":
                hub.broadcast(system, params.get("key"), params.get("value"))
                logger.info(f"[ProcedureEngine] Step: Broadcast {params.get('key')}")
            else:
                res = accept_action(system, action, params)
                logger.info(f"[ProcedureEngine] Step: {action} on {system} -> {res.get('message')}")
                
        logger.info(f"[ProcedureEngine] {protocol['name']} completed.")

def get_procedure_engine():
    return ProcedureEngine.get_instance()

import asyncio
import time
import uuid
import logging
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    ALPHA = 1    # Critical (OPS commands, Security)
    BETA = 2     # Operational (Personnel, Status)
    GAMMA = 3    # Research (KB, Memory Alpha)

class TaskState(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SHELVED = "SHELVED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"

class OpsTask:
    def __init__(self, session_id: str, query: str, priority: TaskPriority = TaskPriority.GAMMA):
        self.pid = f"0x{uuid.uuid4().hex[:4].upper()}"
        self.session_id = session_id
        self.query = query
        self.priority = priority
        self.state = TaskState.PENDING
        self.created_at = time.time()
        self.started_at = 0.0
        self.tools_invoked = []
        self.async_task: Optional[asyncio.Task] = None

class OpsRegistry:
    _instance: Optional['OpsRegistry'] = None

    def __init__(self):
        self.tasks: Dict[str, OpsTask] = {} # PID -> OpsTask
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def register_task(self, session_id: str, query: str, priority: TaskPriority = TaskPriority.GAMMA) -> OpsTask:
        async with self._lock:
            task = OpsTask(session_id, query, priority)
            self.tasks[task.pid] = task
            logger.info(f"[OPS] Task Registered: {task.pid} [{priority.name}] for Session {session_id}")
            return task

    async def update_state(self, pid: str, state: TaskState):
        async with self._lock:
            if pid in self.tasks:
                self.tasks[pid].state = state
                if state == TaskState.RUNNING:
                    self.tasks[pid].started_at = time.time()
                logger.debug(f"[OPS] Task {pid} state updated to {state.value}")

    async def get_active_tasks(self) -> List[OpsTask]:
        async with self._lock:
            return [t for t in self.tasks.values() if t.state in [TaskState.RUNNING, TaskState.PENDING, TaskState.SHELVED]]

    async def abort_task(self, pid: str) -> bool:
        async with self._lock:
            if pid in self.tasks:
                task = self.tasks[pid]
                if task.async_task and not task.async_task.done():
                    task.async_task.cancel()
                    task.state = TaskState.ABORTED
                    logger.warning(f"[OPS] Task {pid} ABORTED by operator.")
                    return True
            return False

    async def set_priority(self, pid: str, priority: TaskPriority) -> bool:
        async with self._lock:
            if pid in self.tasks:
                self.tasks[pid].priority = priority
                logger.info(f"[OPS] Task {pid} priority elevated to {priority.name}")
                return True
            return False

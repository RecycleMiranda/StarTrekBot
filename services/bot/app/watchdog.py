import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SystemWatchdog:
    """
    Monitors system health and AI performance metrics.
    Triggers emergency bypass if stability thresholds are breached.
    """
    _instance = None
    
    def __init__(self):
        self.start_time = time.time()
        self.heartbeat_count = 0
        self.last_latency = 0.0
        self.error_count = 0
        self.stability_score = 1.0 # 0.0 to 1.0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_heartbeat(self):
        self.heartbeat_count += 1

    def update_latency(self, latency: float):
        self.last_latency = latency
        # Simple stability penalty for high latency (> 15s)
        if latency > 15.0:
            self.stability_score = max(0.5, self.stability_score - 0.05)
        else:
            self.stability_score = min(1.0, self.stability_score + 0.05)

    def record_error(self, severity: str = "warning"):
        self.error_count += 1
        penalty = 0.1 if severity == "critical" else 0.02
        self.stability_score = max(0.0, self.stability_score - penalty)

    def get_system_integrity(self) -> Dict[str, Any]:
        """Returns a snapshot of system resilience metrics."""
        status = "OPTIMAL" if self.stability_score > 0.8 else ("DEGRADED" if self.stability_score > 0.4 else "CRITICAL")
        return {
            "uptime": int(time.time() - self.start_time),
            "stability": f"{self.stability_score * 100:.1f}%",
            "status": status,
            "last_latency": f"{self.last_latency:.2f}s",
            "errors": self.error_count
        }

def get_watchdog():
    return SystemWatchdog.get_instance()

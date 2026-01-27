import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EmergencyKernel:
    """
    Static redundant logic core. Contains hardcoded responses for mission-critical
    failures when the Neural Link (AI) is offline or unstable.
    """
    
    def __init__(self):
        self.emergency_responses = {
            "status": "EMERGENCY KERNEL ACTIVE: Systems nominal on static backup.",
            "shield": "IMPERATIVE: Shields raised to 100% via Static Bypass.",
            "alert": "IMPERATIVE: Yellow Alert engaged via Emergency Protocol.",
            "default": "Subspace interference detected. AI Logic severed. Reverting to Static Command Kernel."
        }

    def execute_static_command(self, query: str) -> Dict[str, Any]:
        """Maps query keywords to hardcoded static responses."""
        q = query.lower()
        
        if any(k in q for k in ["status", "report", "状态"]):
            reply = self.emergency_responses["status"]
        elif any(k in q for k in ["shield", "护盾"]):
            reply = self.emergency_responses["shield"]
        elif any(k in q for k in ["alert", "警报"]):
            reply = self.emergency_responses["alert"]
        else:
            reply = self.emergency_responses["default"]
            
        return {
            "ok": True,
            "reply": reply,
            "intent": "reply",
            "source": "EMERGENCY_STATIC_KERNEL"
        }

_kernel = None
def get_emergency_kernel():
    global _kernel
    if not _kernel:
        _kernel = EmergencyKernel()
    return _kernel

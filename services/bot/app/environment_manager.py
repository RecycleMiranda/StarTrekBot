import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EnvironmentManager:
    """
    ADS 6.0: Environment Awareness Layer.
    Tracks external factors that impact system performance (e.g. EM interference, Gravity).
    """
    _instance = None
    _conditions: Dict[str, float] = {
        "STANDARD_VACUUM": 1.0,
        "EM_INTERFERENCE": 0.0,   # 0 to 1.0 (1.0 = total blackout)
        "GRAVIMETRIC_DISTORTION": 0.0,
        "RADIATION_LEVEL": 0.05,  # Background radiation
        "CHRONITON_FLUX": 0.0
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EnvironmentManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_condition(self, key: str, value: float):
        """Sets an environmental factor (usually 0.0 to 1.0)."""
        self._conditions[key] = value
        logger.info(f"[EnvironmentManager] Condition Updated: {key} = {value}")
        
        # Broadcast to SignalHub
        from .signal_hub import get_signal_hub
        get_signal_hub().broadcast("environment", f"ENV_{key.upper()}", value)

    def get_factor(self, factor_type: str) -> float:
        """Returns the current scaling factor for a specific system type."""
        # Mapping logic for how environment affects systems
        if factor_type == "sensors":
            return max(0.1, 1.0 - self._conditions.get("EM_INTERFERENCE", 0.0) * 0.8)
        
        if factor_type == "communications":
            return max(0.0, 1.0 - self._conditions.get("EM_INTERFERENCE", 0.0))
            
        if factor_type == "navigation":
            return max(0.2, 1.0 - self._conditions.get("GRAVIMETRIC_DISTORTION", 0.0))
            
        return 1.0

    def get_all_conditions(self) -> Dict[str, float]:
        return self._conditions.copy()

def get_environment_manager():
    return EnvironmentManager.get_instance()

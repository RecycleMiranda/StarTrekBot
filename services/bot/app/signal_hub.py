import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SignalHub:
    """
    ADS 6.0: The Central Signal Exchange Hub (ODN Bus).
    Maintains a global state of signals broadcast by various ship systems.
    """
    _instance = None
    _signals: Dict[str, Any] = {}
    _origins: Dict[str, str] = {} # signal_key -> origin_system

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SignalHub, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def broadcast(self, origin_system: str, signal_key: str, value: Any):
        """
        Broadcasts a signal to the bus.
        """
        self._signals[signal_key] = value
        self._origins[signal_key] = origin_system
        logger.debug(f"[SignalHub] BROADCAST: {origin_system} -> {signal_key} = {value}")

    def query_signal(self, signal_key: str) -> Any:
        """
        Queries the current value of a signal.
        """
        return self._signals.get(signal_key)

    def get_all_signals(self) -> Dict[str, Any]:
        """
        Returns a snapshot of all active signals.
        """
        return self._signals.copy()

    def clear_signals(self):
        """
        Reset the bus (Emergency/Reboot only).
        """
        self._signals.clear()
        self._origins.clear()
        logger.warning("[SignalHub] BUS RESET: All signals cleared.")

def get_signal_hub():
    return SignalHub.get_instance()

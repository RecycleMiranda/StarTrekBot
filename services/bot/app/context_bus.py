import os
import datetime
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def get_odn_snapshot(session_id: str, user_profile: dict = None) -> Dict[str, Any]:
    """
    Generates a structured 'ODN Snapshot' representing the current ship/system state.
    This provides the AI with its 'Proprioception' (Self-Awareness).
    """
    # Placeholder for actual system status gathering
    # In a real scenario, this would poll sensors, reactor, etc.
    
    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "stardate": f"{79069.1:.1f}", # Calculated for 2026
        "session": {
            "id": session_id,
            "mode": "ACTIVE_INTERACTION",
            "clearance": user_profile.get("clearance", 0) if user_profile else 0,
            "alert_level": os.getenv("SHIP_ALERT_LEVEL", "GREEN")
        },
        "subsystems": {
            "main_odn": "OPTIMAL",
            "sensor_fusion": "ACTIVE",
            "memory_alpha_link": "STABLE",
            "engineer_core": "STANDBY",
            "researcher_core": "IDLE"
        },
        "proprioception": {
            "system_version": "SS-1.0-RC1",
            "core_identity": "StarTrekBot Main Computer",
            "integrity_score": 0.99,
            "last_diagnostic": "79068.5"
        }
    }
    
    return snapshot

def format_snapshot_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Formats the JSON snapshot into a highly readable block for the AI."""
    import json
    return f"CURRENT ODN SNAPSHOT (PROPRIOCEPTION):\n{json.dumps(snapshot, indent=2)}"

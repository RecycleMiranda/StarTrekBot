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
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    
    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "stardate": f"{79069.1:.1f}", # Calculated for 2026
        "session": {
            "id": session_id,
            "mode": "ACTIVE_INTERACTION",
            "clearance": user_profile.get("clearance", 0) if user_profile else 0,
            "alert_level": ss.alert_status.value
        },
        "ship_status": {
            "power": {
                "warp_core_output": f"{ss.warp_core_output:.1f}%",
                "fuel_reserves": f"{ss.fuel_reserves:.1f}%",
                "eps_grid": ss.subsystems.get("eps_grid", SubsystemState.ONLINE).value
            },
            "defense": {
                "shields_active": ss.shields_active,
                "shield_integrity": f"{ss.shield_integrity:.1f}%",
                "weapons_status": ss.subsystems.get("weapons", SubsystemState.ONLINE).value
            },
            "hull": {
                "integrity": f"{ss.hull_integrity:.1f}%",
                "structural_integrity_field": ss.subsystems.get("structural_integrity", SubsystemState.ONLINE).value
            },
            "life_support": ss.subsystems.get("life_support", SubsystemState.ONLINE).value,
            "casualties": ss.casualties
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

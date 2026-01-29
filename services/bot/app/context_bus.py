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
    from .signal_hub import get_signal_hub
    from .environment_manager import get_environment_manager
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
                "warp_core_output": f"{ss.get_component('warp_core')['metrics']['output'].get('current_value', 98.4):.1f}%",
                "warp_core_eff": f"{ss.get_subsystem_efficiency('warp_core'):.2f}",
                "fuel_reserves": f"{ss.get_component('batteries')['metrics']['charge_level'].get('current_value', 100.0):.1f}%",
                "eps_grid": ss.get_component("eps_grid")["current_state"]
            },
            "defense": {
                "shields_active": ss.get_component("shields")["current_state"] == "UP",
                "shield_eff": f"{ss.get_subsystem_efficiency('shields'):.2f}",
                "shield_integrity": f"{ss.get_component('shields')['metrics']['integrity'].get('current_value', 100.0):.1f}%",
                "weapons_status": ss.get_component("phasers")["current_state"],
                "weapons_eff": f"{ss.get_subsystem_efficiency('phasers'):.2f}"
            },
            "hull": {
                "integrity": f"{ss.get_component('sif')['metrics']['field_density'].get('current_value', 100.0):.1f}%",
                "structural_integrity_field": ss.get_component("sif")["current_state"]
            },
            "life_support": ss.get_component("life_support")["current_state"],
            "casualties": "0" 
        },
        "subsystems": {
            "main_odn": "OPTIMAL",
            "sensor_fusion": "ACTIVE",
            "memory_alpha_link": "STABLE",
            "engineer_core": "STANDBY",
            "researcher_core": "IDLE"
        },
        "proprioception": {
            "system_version": "SS-ADS-6.0",
            "core_identity": "StarTrekBot Main Computer (Neural Growth Logic Active)",
            "integrity_score": 0.99,
            "last_diagnostic": "79068.5",
            "environmental_conditions": get_environment_manager().get_all_conditions(),
            "active_odn_signals": get_signal_hub().get_all_signals()
        }
    }
    
    return snapshot

def format_snapshot_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Formats the JSON snapshot into a highly readable block for the AI."""
    import json
    return f"CURRENT ODN SNAPSHOT (PROPRIOCEPTION):\n{json.dumps(snapshot, indent=2)}"

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

    def _safe_get_metric(sys_name: str, metric_key: str, default_val: Any) -> Any:
        try:
            comp = ss.get_component(sys_name)
            if not comp: return default_val
            m_data = comp.get("metrics", {}).get(metric_key, {})
            return m_data.get("current_value", m_data.get("default", default_val))
        except:
            return default_val

    def _safe_get_state(sys_name: str, default_state: str = "UNKNOWN") -> str:
        try:
            comp = ss.get_component(sys_name)
            return comp.get("current_state", default_state) if comp else default_state
        except:
            return default_state
    
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
                "warp_core_output": f"{_safe_get_metric('warp_core', 'output', 98.4):.1f}%",
                "warp_core_eff": f"{ss.get_subsystem_efficiency('warp_core'):.2f}",
                "fuel_reserves": f"{_safe_get_metric('batteries', 'charge_level', 100.0):.1f}%",
                "eps_grid": _safe_get_state("eps_grid", "STABLE")
            },
            "defense": {
                "shields_active": _safe_get_state("shields") == "UP",
                "shield_eff": f"{ss.get_subsystem_efficiency('shields'):.2f}",
                "shield_integrity": f"{_safe_get_metric('shields', 'integrity', 100.0):.1f}%",
                "weapons_status": _safe_get_state("phasers", "OFFLINE"),
                "weapons_eff": f"{ss.get_subsystem_efficiency('phasers'):.2f}"
            },
            "hull": {
                "integrity": f"{_safe_get_metric('sif', 'field_density', 100.0):.1f}%",
                "structural_integrity_field": _safe_get_state("sif", "NOMINAL")
            },
            "life_support": _safe_get_state("life_support", "NOMINAL"),
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

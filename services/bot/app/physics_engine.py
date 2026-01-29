import logging
import math
from typing import Dict, Any, List, Optional
from .signal_hub import get_signal_hub

logger = logging.getLogger(__name__)

class PhysicsEngine:
    _instance = None

    # 24th Century Physical Constants
    C = 299792458.0  # Speed of light (m/s)
    WARP_1_C = 1.0   # Warp 1 = c
    G_CONST = 9.81   # Standard Gravity (m/s^2)
    
    def __init__(self):
        self._formulas = {}
        self._register_core_formulas()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_core_formulas(self):
        """Registers the initial set of physics formulas from the Technical Manual."""
        # Future expansion: Load these from a config file or decorator based system
        pass

    def recalculate(self, system_name: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main entry point for physics calculations.
        Returns a list of side-effect updates to be applied by ShipSystems.
        """
        updates = []
        name = system_name.lower()
        
        # Dispatch logic based on system type
        if "phaser" in name:
            updates.extend(self._calculate_phaser_physics(context))
        elif "deflector" in name:
            updates.extend(self._calculate_deflector_interference(context))
        elif "warp_core" in name or "reactor" in name:
            updates.extend(self._calculate_eps_load_shedding(context))
        elif "comms" in name:
            updates.extend(self._calculate_subspace_decay(context))
        elif "rcs" in name:
            updates.extend(self._calculate_rcs_vectors(context))
            
        return updates

    # --- Domain Logic Methods ---

    def _calculate_phaser_physics(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [TACT] Calculates NDF (Nuclear Disruption Force) ratio based on Phaser Level.
        Ref: TNG Technical Manual 1.6
        """
        updates = []
        metrics = ctx.get("metrics", {})
        
        # Get current yield setting
        yield_setting = 1
        if "yield_setting" in metrics:
            val = metrics["yield_setting"].get("current_value")
            if val is not None:
                yield_setting = int(val)
        
        # Calculate NDF Ratio
        # Level 1-5: 0 (Pure Thermal)
        # Level 7: 1:1
        # Level 16: 1:40 (High Disruption)
        ndf_ratio = 0.0
        if yield_setting >= 16:
            ndf_ratio = 40.0
        elif yield_setting >= 7:
            # Linear interpolation between 1.0 (L7) and 40.0 (L16)
            ndf_ratio = 1.0 + (yield_setting - 7) * (39.0 / 9.0)
        
        # Create update check (avoid infinite loops by checking diff)
        current_ndf = metrics.get("ndf_ratio", {}).get("current_value", -1)
        if abs(current_ndf - ndf_ratio) > 0.1:
            updates.append({
                "system": ctx.get("name"),
                "metric": "ndf_ratio",
                "value": round(ndf_ratio, 2)
            })
            
        return updates

    def _calculate_deflector_interference(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [DEFL] Calculates sensor blind spots based on Deflector output.
        Ref: TNG Technical Manual 1.25
        """
        updates = []
        metrics = ctx.get("metrics", {})
        
        # Check power output (assume default max 100%)
        output = 0.0
        if "output" in metrics:
             output = float(metrics["output"].get("current_value", 0))
        elif "power" in metrics:
             output = float(metrics["power"].get("current_value", 0))

        # Inteference Threshold > 55%
        interference_penalty = 0.0
        if output > 55.0:
            # Linear penalty from 0% at 55 output to 90% at 100 output
            interference_penalty = (output - 55.0) * (90.0 / 45.0)
            
        # Apply to LRS (Long Range Sensors)
        # We need to know the LRS system name, assuming 'lrs' here
        # In a real implementation, we might query the registry for 'sensors'
        if interference_penalty > 0:
            updates.append({
                "system": "lrs",
                "metric": "interference_penalty",
                "value": round(interference_penalty, 1)
            })
            
        return updates

    def _calculate_eps_load_shedding(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [EPS] Triggers load shedding if Warp Core output drops critically.
        Ref: TNG Technical Manual 1.22
        """
        updates = []
        metrics = ctx.get("metrics", {})
        
        output = 100.0
        if "output" in metrics:
            output = float(metrics["output"].get("current_value", 100.0))
            
        # Critical Thresholds
        if output < 20.0:
            # Drop Non-Essential
            updates.append({"system": "holodecks", "metric": "power_state", "value": 0}) # 0 = OFF
            updates.append({"system": "replicators", "metric": "efficiency", "value": 0})
        elif output < 40.0:
            # Warning level
            pass
            
        return updates

    def _calculate_subspace_decay(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [COMM] Calculates effective range based on subspace signal decay.
        Ref: TNG Technical Manual 1.28 (22.65 ly limit)
        """
        updates = []
        # Nominal range is 22.65 ly at standard output
        # If output power drops, range drops linearly
        metrics = ctx.get("metrics", {})
        
        signal_strength = 100.0
        if "signal_strength" in metrics:
             signal_strength = float(metrics["signal_strength"].get("current_value", 100.0))
             
        effective_range = 22.65 * (signal_strength / 100.0)
        
        updates.append({
            "system": ctx.get("name"), # Self-update
            "metric": "effective_range",
            "value": round(effective_range, 2)
        })
        return updates

    def _calculate_rcs_vectors(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [RCS] Adjusts thruster vectors based on saucer separation state.
        Ref: TNG Technical Manual 1.24
        """
        updates = []
        # In a full engine, we'd check the global 'saucer_sep' state
        # For now, we simulate a self-adjustment based on a 'mode' metric if it existed
        pass
        return updates
        """Converts Cochrane field strength to multiples of c (approximate)."""
        if cochrane < 1.0:
            return cochrane # Subspace field modulation
        # TNG Scale: v = w^(10/3) * c is for Warp Factor, not raw Cochrane, 
        # but often Cochrane ~ Warp Factor in field stress discussions.
        # For pure field strength (mC), we treat 1000 mC = 1 Cochrane.
        return cochrane 

    def watts_to_joules(self, watts: float, seconds: float) -> float:
        return watts * seconds

def get_physics_engine():
    return PhysicsEngine.get_instance()

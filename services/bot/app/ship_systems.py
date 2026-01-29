import logging
import json
import os
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class AlertStatus(Enum):
    NORMAL = "NORMAL"
    YELLOW = "YELLOW"
    RED = "RED"

# SubsystemState is now dynamic string-based in the new architecture, 
# but we keep this for legacy compatibility until full migration.
class SubsystemState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DAMAGED = "DAMAGED"

class ShipSystems:
    _instance = None
    
    def __init__(self):
        self.alert_status = AlertStatus.NORMAL
        self.shields_active = False # Legacy boolean, sync logic needed
        self.shield_integrity = 100 # Legacy
        
        # MSD Architecture Containers
        self.msd_registry = {}      # The raw JSON tree
        self.component_map = {}     # Flat map: "warp_core" -> component_obj
        
        # Load the graph
        self._load_msd_registry()

        # Legacy TIER_MAP emulation (auto-generated from graph)
        self.TIER_MAP = self._generate_tier_map()
        
        # Energy Model (Unified)
        self.power_output_mw = 12500000.0 
        self.battery_reserve_pct = 100.0
        self.current_load_mw = 4200000.0
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_msd_registry(self):
        """Loads the Unified MSD Registry from JSON."""
        try:
            reg_path = os.path.join(os.path.dirname(__file__), "config", "msd_registry.json")
            with open(reg_path, "r") as f:
                self.msd_registry = json.load(f)
            
            # Build valid component map recursively
            self._recursive_build_map(self.msd_registry)
            logger.info(f"[ShipSystems] MSD Registry Loaded. {len(self.component_map)} components mapped.")
            print(f"DEBUG: Loaded keys: {list(self.component_map.keys())}")
            
        except Exception as e:
            logger.error(f"[ShipSystems] CRITICAL: Failed to load MSD Registry: {e}")
            print(f"DEBUG CRITICAL ERROR: {e}")
            # Fallback to minimal dict to prevent crash
            self.component_map = {}

    def _recursive_build_map(self, node: dict, prefix: str = ""):
        """Traverses the tree to index components by name and aliases."""
        for key, value in node.items():
            if not isinstance(value, dict):
                continue

            # Case A: Component Leaf (Has Metrics)
            if "metrics" in value:
                # Store mutable state directly in the object
                if "current_state" not in value:
                    value["current_state"] = value.get("default_state", "OFFLINE")
                
                # Index by key
                self.component_map[key] = value
                
                # Index by aliases
                for alias in value.get("aliases", []):
                    self.component_map[alias] = value
            
            # Case B: System Group (Has 'components' sub-dict)
            elif "components" in value:
                self._recursive_build_map(value["components"], prefix=f"{key}.")
            
            # Case C: Organizational Container (e.g. "engineering") -> Recurse values
            else:
                self._recursive_build_map(value, prefix=f"{key}.")

    def _generate_tier_map(self) -> Dict[str, int]:
        """Auto-generates tier map for legacy compatibility based on importance."""
        # Simple heuristic mapping for now
        tiers = {}
        for key, comp in self.component_map.items():
            # Default to mid-tier
            tiers[key] = 3
            if "core" in key or "reactor" in key or "eps" in key: tiers[key] = 1
            if "shield" in key or "weapon" in key: tiers[key] = 2
            if "life" in key: tiers[key] = 4
            if "replicator" in key: tiers[key] = 5
        return tiers

    def get_component(self, name: str) -> Optional[Dict]:
        """Retrieves a component object by name or alias, with dynamic efficiency."""
        comp = self.component_map.get(name.lower())
        if comp:
            # Inject real-time efficiency
            comp["efficiency"] = self.calculate_efficiency(name.lower())
        return comp

    def calculate_efficiency(self, name: str, visited: set = None) -> float:
        """
        ADS 6.0: Functional Graph Efficiency Calculation.
        Recursively calculates a system's efficiency based on its dependencies.
        """
        if visited is None: visited = set()
        
        comp = self.component_map.get(name.lower())
        if not comp or name.lower() in visited: return 100.0
        visited.add(name.lower())
        
        # 1. Base Health (Damage/State)
        state = comp.get("current_state", "OFFLINE")
        if state in ["OFFLINE", "DAMAGED", "FAILING"]: return 0.0
        
        # 2. Dependency Check (The Cascade)
        deps = comp.get("dependencies", [])
        if not deps: return 100.0
        
        dep_efficiencies = []
        for dep_key in deps:
            eff = self.calculate_efficiency(dep_key, visited)
            dep_efficiencies.append(eff)
            
        # Overall efficiency is limited by the weakest link in the chain
        return min(dep_efficiencies) if dep_efficiencies else 100.0

    def set_subsystem(self, name: str, state_val: Any) -> str:
        """
        Unified state setter. 
        Supports both Enum (Legacy) and String (New) states.
        Triggers Metric Cascade logic.
        """
        comp = self.get_component(name)
        if not comp:
            return f"找不到组件: {name} (Component not found in MSD)."
            
        if isinstance(state_val, (int, float)) or (isinstance(state_val, str) and state_val.replace(".", "", 1).isdigit()):
            # [ADS 3.5] Smart Redirect: Detected numeric input for state -> Redirect to Metric Adjustment
            val = float(state_val)
            
            # Heuristic: Find primary metric
            target_metric = "output" # Default
            if "shield" in name: target_metric = "integrity"
            elif "impulse" in name: target_metric = "thrust"
            elif "deflector" in name: target_metric = "particle_dispersion"
            elif "phaser" in name: target_metric = "yield_setting"
            elif "battery" in name or "cell" in name: target_metric = "charge_level"
            
            # Check if metric actually exists, otherwise grab the first one
            metrics = comp.get("metrics", {})
            if target_metric not in metrics and metrics:
                target_metric = list(metrics.keys())[0]
                
            return self.set_metric_value(name, target_metric, val)

        # Normalize state
        target_state = state_val
        if isinstance(state_val, Enum):
            target_state = state_val.value
            
        target_state = target_state.upper()
        
        # Validation
        valid_states = comp.get("states", [])
        if valid_states and target_state not in valid_states:
            # Try to map generic ONLINE/OFFLINE to component specific
            if target_state == "ONLINE":
                # Find the first active state if ONLINE isn't explicitly defined
                active_candidates = [s for s in valid_states if s not in ["OFFLINE", "FAILING", "DAMAGED"]]
                if active_candidates:
                    # Priority 1: Use specific default_state if it's active
                    ds = comp.get("default_state")
                    if ds in active_candidates:
                        target_state = ds
                    else:
                        # Priority 2: Use STANDBY if available
                        if "STANDBY" in active_candidates:
                            target_state = "STANDBY"
                        # Priority 3: Use first available active state
                        else:
                            target_state = active_candidates[0]
                else:
                    # Absolute fallback to registry default if no active states found
                    target_state = comp.get("default_state", "ONLINE")
            elif target_state == "OFFLINE" and "OFFLINE" in valid_states:
                target_state = "OFFLINE"
            else:
                return f"无效状态 '{target_state}'。有效值: {valid_states}"

        # Prepare for state change tracking
        old_state = comp.get("current_state", "UNKNOWN")
        if old_state == target_state:
             return f"[NO_CHANGE] {comp.get('name', name)} is already {target_state}."

        # Update State
        comp["current_state"] = target_state
        state_display = target_state
        
        # --- METRIC CASCADE LOGIC (The Core Fix) ---
        mapped_changes = []
        metrics = comp.get("metrics", {})
        for m_key, m_data in metrics.items():
            link_map = m_data.get("linked_to_state", {})
            
            # If current state dictates a specific metric value (e.g. OFFLINE -> 0)
            if target_state in link_map:
                forced_val = link_map[target_state]
                m_data["current_value"] = forced_val
                mapped_changes.append(f"{m_key} -> {forced_val}{m_data.get('unit','')}")
            
            # If transitioning FROM a zero-state TO active, restore nominal if undefined
            elif "current_value" not in m_data or m_data["current_value"] == 0:
                 if "nominal" in m_data:
                     m_data["current_value"] = m_data["nominal"]
        
        # Sync legacy attributes for backward compat
        if "shield" in name and target_state in ["UP", "ONLINE"]:
             self.shields_active = True
        elif "shield" in name:
             self.shields_active = False

        msg = f"{comp.get('name')} 状态已变更为 [{target_state}]。"
        if mapped_changes:
            msg += f" 联动指标调整: {', '.join(mapped_changes)}。"
            
        return msg

    def set_metric_value(self, system: str, metric: str, value: float) -> str:
        """
        [ADS 3.5] Internal handler for metric updates. 
        Updates the value and returns a confirmation string.
        """
        comp = self.get_component(system)
        if not comp: return f"System '{system}' not found."
        
        metrics = comp.get("metrics", {})
        if metric not in metrics:
             return f"Metric '{metric}' not found on system '{system}'."
             
        # Update
        metrics[metric]["current_value"] = value
        
        # Reverse Cascade: If setting output > 0, ensure system is NOT OFFLINE
        if value > 0 and comp.get("current_state") == "OFFLINE":
             if comp.get("default_state"):
                 comp["current_state"] = comp.get("default_state")
                 return f"Confirmed. {comp.get('name')} {metric} set to {value}. [AUTO-START] System brought ONLINE to support non-zero output."
        
        return f"Confirmed. {comp.get('name')} {metric} set to {value}{metrics[metric].get('unit','')}."

    def get_metric(self, system: str, metric: str) -> str:
        comp = self.get_component(system)
        if not comp: return "N/A"
        
        m_data = comp.get("metrics", {}).get(metric)
        if not m_data: return "N/A"
        
        val = m_data.get("current_value", m_data.get("default", 0))
        unit = m_data.get("unit", "")
        return f"{val}{unit}"

    # --- Legacy Adaptor Methods ---
    
    def is_subsystem_online(self, name: str) -> bool:
        comp = self.get_component(name)
        if not comp: return False
        return comp.get("current_state") not in ["OFFLINE", "DAMAGED", "FAILING"]

    def is_subsystem_operational(self, name: str) -> bool:
        return self.is_subsystem_online(name) # Simplified for now

    def set_alert(self, level: str, validate_current: Optional[str] = None) -> (str, Optional[str]):
        # Keep original alert logic, it's global not component specific
        level = level.upper()
        old_level = self.alert_status
        target = "NORMAL"
        if level in ["RED", "红色"]: target = "RED"
        if level in ["YELLOW", "黄色"]: target = "YELLOW"
        
        if validate_current and target == "NORMAL":
             if old_level.value != validate_current.upper():
                  return f"Alert condition mismatch.", None

        if old_level.value == target:
            return "Alert status unchanged.", None

        asset_base = "/app/services/bot/app/static/assets/alerts"
        gif_map = {"RED": f"{asset_base}/red_alert.gif", "YELLOW": f"{asset_base}/yellow_alert.gif"}

        if target == "RED":
            self.alert_status = AlertStatus.RED
            self.set_subsystem("shields", "UP") 
            self.set_subsystem("phasers", "STANDBY")
            return "RED ALERT initiated. Shields UP. Weapons STANDBY.", gif_map.get("RED")
        elif target == "YELLOW":
            self.alert_status = AlertStatus.YELLOW
            self.set_subsystem("shields", "UP")
            return "Yellow Alert. Shields UP.", gif_map.get("YELLOW")
        else:
            self.alert_status = AlertStatus.NORMAL
            self.set_subsystem("shields", "OFFLINE")
            self.set_subsystem("phasers", "OFFLINE")
            return "Condition Green. Systems normalized.", None

    def get_status_report(self) -> Dict:
        """Generates a full MSD status report."""
        # This replaces the old get_status dict construction
        # We can just return the entire MSD tree? No, cleaner to flatten or structure for AI
        return {
            "alert": self.alert_status.value,
            "msd_manifest": self._get_flattened_metrics()
        }

    def _get_flattened_metrics(self) -> Dict:
        """Returns a flat key-value of critical systems for AI context."""
        flat = {}
        for key, comp in self.component_map.items():
            # Skip aliases in output to avoid duplications
            name = comp.get("name") or ""
            if key != name.lower().replace(" ", "_") and key not in ["warp_core", "shields", "phasers"]:
                 continue 
                 
            metrics_str = []
            for m_k, m_v in comp.get("metrics", {}).items():
                val = m_v.get("current_value", m_v.get("default"))
                unit = m_v.get("unit", "")
                metrics_str.append(f"{m_k}: {val}{unit}")
            
            flat[key] = {
                "state": comp.get("current_state"),
                "metrics": ", ".join(metrics_str)
            }
        return flat

def get_ship_systems():
    return ShipSystems.get_instance()

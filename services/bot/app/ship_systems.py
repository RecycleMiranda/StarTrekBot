import logging
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class AlertStatus(Enum):
    NORMAL = "NORMAL"
    YELLOW = "YELLOW"
    RED = "RED"

class SubsystemState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DAMAGED = "DAMAGED"

class ShipSystems:
    _instance = None
    
    # Tier mapping for priority logic
    TIER_MAP = {
        "main_reactor": 1, "eps_grid": 1, "auxiliary_power": 1,
        "shields": 2, "phasers": 2, "phase_cannons": 2, "torpedoes": 2, "sif": 2, "weapons": 2, "structural_integrity": 2,
        "warp_drive": 3, "impulse_engines": 3, "nav_deflector": 3,
        "life_support": 4, "computer_core": 4, "sensors": 4, "comms": 4,
        "transporters": 5, "replicators": 5, "holodecks": 5, "emh": 5, "waste_management": 5
    }

    # Dependency mapping
    DEPENDENCIES = {
        "eps_grid": ["main_reactor"],
        "shields": ["eps_grid"],
        "phasers": ["eps_grid"],
        "phase_cannons": ["eps_grid"],
        "torpedoes": ["eps_grid"],
        "weapons": ["eps_grid"],
        "sif": ["eps_grid"],
        "warp_drive": ["main_reactor"],
        "impulse_engines": ["eps_grid"],
        "nav_deflector": ["eps_grid"],
        "life_support": ["eps_grid"],
        "waste_management": ["eps_grid"],
        "computer_core": ["eps_grid"],
        "sensors": ["eps_grid"],
        "comms": ["eps_grid"],
        "transporters": ["eps_grid"],
        "replicators": ["eps_grid"],
        "holodecks": ["eps_grid"],
        "emh": ["eps_grid", "computer_core"]
    }

    def __init__(self):
        self.alert_status = AlertStatus.NORMAL
        self.shields_active = False
        self.shield_integrity = 100
        
        # Initialize all known subsystems to ONLINE
        self.subsystems: Dict[str, SubsystemState] = {
            name: SubsystemState.ONLINE for name in self.TIER_MAP
        }
        # Specialized states
        self.subsystems["emh"] = SubsystemState.OFFLINE # EMH starts offline
        
        # New MA Standard Metrics
        self.warp_core_output = 98.4  # Percent
        self.fuel_reserves = 85.0     # Percent (Deuterium/Antimatter)
        self.hull_integrity = 100.0   # Percent
        self.casualties = 0           # Count
        
        # --- PHASE 4: EPS ENERGY MODEL ---
        self.power_output_mw = 12500000.0  # Total Warp Core Output in MW (Galaxy Class spec)
        self.battery_reserve_pct = 100.0   # Emergency batteries
        self.current_load_mw = 4200000.0   # Base load (Life Support, Computers, structural integrity)
        
        # Power drain mapping (Nominal costs in MW)
        self.POWER_DRAIN = {
            "shields": 1500000.0,
            "phasers": 800000.0,
            "warp_drive": 3000000.0,
            "transporters": 500000.0,
            "holodecks": 300000.0,
            "replicators": 200000.0,
            "eps_grid": 100000.0,
            "life_support": 1000000.0,
            "computer_core": 800000.0,
            "sensors": 400000.0
        }
        
        # --- PHASE 4: DYNAMIC AUXILIARY STATE ---
        self.auxiliary_state: Dict[str, str] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_alert(self, level: str, validate_current: Optional[str] = None) -> (str, Optional[str]):
        level = level.upper()
        old_level = self.alert_status
        
        # Mapping to normalized strings
        target = "NORMAL"
        if level in ["RED", "红色"]: target = "RED"
        if level in ["YELLOW", "黄色"]: target = "YELLOW"
        
        # Validation for cancellation targeting a specific level
        if validate_current and target == "NORMAL":
            vc = validate_current.upper()
            if old_level.value != vc:
                display_names = {"RED": "红色警报", "YELLOW": "黄色警报", "NORMAL": "正常巡航模式"}
                return f"无法完成：当前处于 {display_names.get(old_level.value)}，而非 {display_names.get(vc)}，", None

        # 1. State: Already in target
        if old_level.value == target:
            if target == "RED": return "警报状态未变更：当前已处于红色警报状态，", None
            if target == "YELLOW": return "警报状态未变更：当前已处于黄色警报状态，", None
            return "舰船当前已处于正常巡航模式，", None

        # Alert GIF paths (Local to Docker container)
        # We assume the user will place these in the static/assets/alerts/ folder
        asset_base = "/app/services/bot/app/static/assets/alerts"
        gif_map = {
            "RED": f"{asset_base}/red_alert.gif",
            "YELLOW": f"{asset_base}/yellow_alert.gif"
        }

        # 2. Transition Logic
        if target == "RED":
            self.alert_status = AlertStatus.RED
            self.shields_active = True
            return "全体注意，红色警报，", gif_map.get("RED")
            
        elif target == "YELLOW":
            self.alert_status = AlertStatus.YELLOW
            return "全体注意，黄色警报，", gif_map.get("YELLOW")
            
        else: # NORMAL
            self.alert_status = AlertStatus.NORMAL
            return "警报已解除，正常巡航模式已恢复，", None

    def toggle_shields(self, active: bool) -> str:
        if active and not self.is_subsystem_operational("shields"):
            return "无法执行：护盾核心或电力供应下线，"
        
        self.shields_active = active
        return f"护盾已{'升起' if active else '降下'}，当前完整度：{self.shield_integrity}%，"

    def get_shield_status(self) -> str:
        state = "已升起" if self.shields_active else "未升起"
        return f"护盾状态：{state}\n完整度：{self.shield_integrity}%"

    def set_subsystem(self, name: str, state: SubsystemState) -> str:
        if name in self.subsystems:
            self.subsystems[name] = state
            status_text = {
                SubsystemState.ONLINE: "已上线",
                SubsystemState.OFFLINE: "已下线",
                SubsystemState.DAMAGED: "受损"
            }.get(state, "状态不明")
            
            # Map common internal names to Chinese for the response
            display_names = {
                "weapons": "武器系统",
                "shields": "护盾系统",
                "phasers": "相位炮",
                "phase_cannons": "相位加农炮",
                "weapons": "武器阵列",
                "torpedoes": "鱼雷系统",
                "comms": "通讯系统",
                "transporters": "传送器",
                "replicators": "复制机",
                "holodecks": "全息甲板",
                "waste_management": "废弃物处理系统",
                "structural_integrity": "结构完整性场",
                "sif": "SIF发生器"
            }
            display_name = display_names.get(name.lower(), name.upper())
            return f"{display_name}{status_text}，"
        return f"找不到子系统: {name}，"

    def is_subsystem_online(self, name: str) -> bool:
        """Checks if the system itself is set to ONLINE."""
        return self.subsystems.get(name) == SubsystemState.ONLINE

    def is_subsystem_operational(self, name: str) -> bool:
        """Recursively checks if the system and all its dependencies are ONLINE."""
        if self.subsystems.get(name) != SubsystemState.ONLINE:
            return False
            
        # Check dependencies
        deps = self.DEPENDENCIES.get(name, [])
        for dep in deps:
            if not self.is_subsystem_operational(dep):
                return False
        
        return True

    def get_power_status(self) -> Dict:
        """Calculates current load vs output."""
        operational_output = self.power_output_mw if self.is_subsystem_online("main_reactor") else 0.0
        
        # Calculate load of all ONLINE systems
        active_load = self.current_load_mw # Start with base load
        for name, state in self.subsystems.items():
            if state == SubsystemState.ONLINE:
                active_load += self.POWER_DRAIN.get(name, 0.0)
        
        # Also add load for active shields
        if self.shields_active:
            active_load += self.POWER_DRAIN.get("shields", 1500000.0)
            
        load_pct = (active_load / self.power_output_mw) * 100 if self.power_output_mw > 0 else 100.0
        
        return {
            "total_output_mw": operational_output,
            "active_load_mw": active_load,
            "load_percent": round(load_pct, 2),
            "reserve_power": self.battery_reserve_pct if operational_output == 0 else 100.0,
            "status": "STABLE" if active_load <= operational_output else "DEFICIT"
        }

    def get_system_report(self) -> Dict:
        """Returns a full categorized status report."""
        report = {"power_grid": self.get_power_status()}
        for tier in range(1, 6):
            systems_in_tier = [name for name, t in self.TIER_MAP.items() if t == tier]
            report[f"Tier_{tier}"] = {
                name: {
                    "state": self.subsystems[name].value,
                    "operational": self.is_subsystem_operational(name)
                } for name in systems_in_tier
            }
        return report

def get_ship_systems():
    return ShipSystems.get_instance()

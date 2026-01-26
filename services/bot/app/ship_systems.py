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
        "shields": 2, "phasers": 2, "torpedoes": 2, "sif": 2,
        "warp_drive": 3, "impulse_engines": 3, "nav_deflector": 3,
        "life_support": 4, "computer_core": 4, "sensors": 4, "comms": 4,
        "transporters": 5, "replicators": 5, "holodecks": 5, "emh": 5
    }

    # Dependency mapping
    DEPENDENCIES = {
        "eps_grid": ["main_reactor"],
        "shields": ["eps_grid"],
        "phasers": ["eps_grid"],
        "torpedoes": ["eps_grid"],
        "sif": ["eps_grid"],
        "warp_drive": ["main_reactor"],
        "impulse_engines": ["eps_grid"],
        "nav_deflector": ["eps_grid"],
        "life_support": ["eps_grid"],
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

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_alert(self, level: str) -> str:
        level = level.upper()
        old_level = self.alert_status
        
        # Mapping to normalized strings
        target = "NORMAL"
        if level in ["RED", "红色"]: target = "RED"
        if level in ["YELLOW", "黄色"]: target = "YELLOW"
        
        # 1. State: Already in target
        if old_level.value == target:
            if target == "RED": return "⚠️ 警报状态未变更：当前已处于红色警报状态。"
            if target == "YELLOW": return "⚠️ 警报状态未变更：当前已处于黄色警报状态。"
            return "ℹ️ 舰船当前已处于正常巡航模式。"

        # 2. Transition Logic
        if target == "RED":
            self.alert_status = AlertStatus.RED
            self.shields_active = True
            return "✅ 全体注意，红色警报！"
            
        elif target == "YELLOW":
            self.alert_status = AlertStatus.YELLOW
            return "⚠️ 全体注意，黄色警报！"
            
        else: # NORMAL
            self.alert_status = AlertStatus.NORMAL
            return "噔噔噔"

    def toggle_shields(self, active: bool) -> str:
        if active and not self.is_subsystem_operational("shields"):
            return "❌ 无法执行：护盾核心或电力供应下线。"
        
        self.shields_active = active
        return f"✅ 护盾已{'升起' if active else '降下'}。当前完整度：{self.shield_integrity}%"

    def get_shield_status(self) -> str:
        state = "已升起" if self.shields_active else "未升起"
        return f"🛡️ 护盾状态：{state}\n完整度：{self.shield_integrity}%"

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
                "torpedoes": "鱼雷系统",
                "comms": "通讯系统",
                "transporters": "传送器",
                "replicators": "复制机",
                "holodecks": "全息甲板"
            }
            display_name = display_names.get(name.lower(), name.upper())
            return f"{display_name}{status_text}"
        return f"❌ 找不到子系统: {name}"

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

    def get_system_report(self) -> Dict:
        """Returns a full categorized status report."""
        report = {}
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

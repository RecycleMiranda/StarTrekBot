import logging
from enum import Enum
from typing import Dict

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
    
    def __init__(self):
        self.alert_status = AlertStatus.NORMAL
        self.shields_active = False
        self.shield_integrity = 100
        
        # Subsystems Health
        self.subsystems: Dict[str, SubsystemState] = {
            "transporters": SubsystemState.ONLINE,
            "weapons": SubsystemState.ONLINE,
            "communications": SubsystemState.ONLINE,
            "replicator": SubsystemState.ONLINE,
            "emh": SubsystemState.OFFLINE
        }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_alert(self, level: str) -> str:
        level = level.upper()
        if level == "RED":
            self.alert_status = AlertStatus.RED
            self.shields_active = True
            return "✅ 全体注意，红 色 警 报！"
        elif level == "YELLOW":
            self.alert_status = AlertStatus.YELLOW
            return "⚠️ 全体注意，黄 色 警 报！"
        else:
            self.alert_status = AlertStatus.NORMAL
            return "✅ 警报解除，恢复正常运行状态。"

    def toggle_shields(self, active: bool) -> str:
        self.shields_active = active
        if active:
            return f"✅ 护盾已升起。当前完整度：{self.shield_integrity}%"
        else:
            return "✅ 护盾已降下。"

    def get_shield_status(self) -> str:
        state = "已升起" if self.shields_active else "未升起"
        return f"🛡️ 护盾状态：{state}\n完整度：{self.shield_integrity}%"

    def set_subsystem(self, name: str, state: SubsystemState) -> str:
        if name in self.subsystems:
            self.subsystems[name] = state
            status_text = "上线" if state == SubsystemState.ONLINE else "下线"
            return f"✅ {name.capitalize()} 系统已{status_text}。"
        return f"❌ 找不到子系统: {name}"

    def is_subsystem_online(self, name: str) -> bool:
        return self.subsystems.get(name) == SubsystemState.ONLINE

def get_ship_systems():
    return ShipSystems.get_instance()

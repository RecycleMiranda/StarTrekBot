import json
import os
import random
import time
from typing import Dict, List, Optional
from datetime import datetime

# Production Path Logic
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(BASE_DIR, "ARSENAL_REGISTRY.json")
PHASER_PATH = os.path.join(BASE_DIR, "PHASER_REGISTRY.json")
LEDGER_PATH = os.path.join(BASE_DIR, "ARSENAL_LEDGER.log")

class ArsenalLedger:
    @staticmethod
    def log(trn_id: str, actor: str, action: str, item: str, qty: int, source: str, dest: str):
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] [{trn_id}] [{actor}] [{action}] [{item}] [{qty}] [{source}] -> [{dest}]\n"
        with open(LEDGER_PATH, "a") as f:
            f.write(entry)

class Magazine:
    def __init__(self, mag_id: str, zone: str, role: str, base_capacity: int, tier: int):
        self.mag_id = mag_id
        self.zone = zone
        self.role = role
        self.base_capacity = base_capacity
        self.tier = tier 
        self.inventory: Dict[str, int] = {}
        self._init_stock()

    def _init_stock(self):
        fluctuation = 1.0
        if self.zone == "ALPHA":
            fluctuation = random.uniform(0.9, 1.05)
        elif self.zone == "BETA":
            fluctuation = random.uniform(0.95, 1.15)
        elif self.zone == "CORE":
            fluctuation = random.uniform(0.95, 1.05)
            
        target_stock = int(self.base_capacity * fluctuation)
        self.inventory["photon_torpedo_mk25"] = target_stock
        ArsenalLedger.log(f"INIT-{random.randint(1000,9999)}", "SYS_BOOT", "INIT_STOCK", "photon_torpedo_mk25", target_stock, "VOID", self.mag_id)

    def get_stock(self, item_id: str) -> int:
        return self.inventory.get(item_id, 0)

    def add_stock(self, item_id: str, qty: int):
        if item_id not in self.inventory:
            self.inventory[item_id] = 0
        self.inventory[item_id] += qty

    def remove_stock(self, item_id: str, qty: int) -> bool:
        if self.inventory.get(item_id, 0) >= qty:
            self.inventory[item_id] -= qty
            return True
        return False

class BatteryGroup:
    def __init__(self, bat_id: str, zone: str, tube_spec: str, qty_tubes: int, local_mag_cap: int):
        self.bat_id = bat_id
        self.zone = zone
        self.tube_spec = tube_spec
        self.qty_tubes = qty_tubes
        self.local_mag = Magazine(f"MAG-{bat_id}", zone, "BATTERY_LOCAL", local_mag_cap, 1)

class LogisticsManager:
    def __init__(self):
        self.magazines: Dict[str, Magazine] = {}
        self.batteries: Dict[str, BatteryGroup] = {}
        self.registry_data = self._load_json(REGISTRY_PATH)
        self.phaser_data = self._load_json(PHASER_PATH)
        self._initialize_fortress()

    def _load_json(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _initialize_fortress(self):
        self.magazines["ARS-ALPHA-MAIN"] = Magazine("ARS-ALPHA-MAIN", "ALPHA", "SECTOR_HUB", 50000, 2)
        self.magazines["ARS-BETA-MAIN"] = Magazine("ARS-BETA-MAIN", "BETA", "SECTOR_HUB", 80000, 2)
        self.magazines["ARS-KEEL-RES"] = Magazine("ARS-KEEL-RES", "CORE", "STRATEGIC_RES", 500000, 3)

        self._deploy_battery("ALPHA", "Alpha-Prime", "[L25-S12-R+]", 4, 2000)
        self._deploy_battery("ALPHA", "Deep-Alpha", "[L25-S12-R+]", 2, 1000)
        for i in range(1, 9):
            self._deploy_battery("ALPHA", f"Batt-A{i}", "[L18-B06-R-]", 3, 1200)
        for i in range(1, 5):
            self._deploy_battery("ALPHA", f"Pylon-A{i}", "MIXED", 4, 1500)

        self._deploy_battery("BETA", "Beta-Prime", "[L25-S12-R+]", 2, 1000)
        self._deploy_battery("BETA", "Deep-Beta", "[L25-S12-R+]", 2, 1000)
        for i in range(1, 9):
            self._deploy_battery("BETA", f"Batt-B{i}", "[L18-B06-R-]", 3, 1200)
        for i in range(1, 5):
            self._deploy_battery("BETA", f"Pylon-B{i}", "MIXED", 4, 1500)

    def _deploy_battery(self, zone, name, spec, tubes, mag_cap):
        bat = BatteryGroup(name, zone, spec, tubes, mag_cap)
        self.batteries[name] = bat

    def request_transfer(self, source_id: str, dest_id: str, item_id: str, qty: int) -> bool:
        source_mag = self._resolve_mag(source_id)
        if not source_mag: return False
        dest_mag = self._resolve_mag(dest_id)
        if not dest_mag: return False
        if source_mag.remove_stock(item_id, qty):
            dest_mag.add_stock(item_id, qty)
            ArsenalLedger.log(f"TRN-{random.randint(10000,99999)}", "LOGISTICS_BOT", "TRANSFER", item_id, qty, source_id, dest_id)
            return True
        return False

    def _resolve_mag(self, mag_id):
        if mag_id in self.magazines: return self.magazines[mag_id]
        for bat in self.batteries.values():
            if bat.local_mag.mag_id == mag_id: return bat.local_mag
        return None

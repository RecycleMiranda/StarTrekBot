import json
import os
import time
from typing import Dict, Optional

# Production Path Logic
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHASER_REGISTRY_PATH = os.path.join(BASE_DIR, "PHASER_REGISTRY.json")

class Capacitor:
    def __init__(self, spec: dict):
        self.name = spec["name"]
        self.max_mj = spec["capacity_mj"]
        self.current_mj = self.max_mj # Start full
        self.max_discharge = spec["max_discharge_rate"]
        self.recharge_rate = spec["recharge_rate_grid"]

    def discharge(self, requested_mj: float) -> float:
        if self.current_mj <= 0: return 0.0
        actual_draw = min(requested_mj, self.max_discharge)
        if actual_draw > self.current_mj:
            actual_draw = self.current_mj
        self.current_mj -= actual_draw
        return actual_draw

    def recharge_tick(self, available_grid_power: float) -> float:
        deficit = self.max_mj - self.current_mj
        if deficit <= 0: return 0.0
        draw = min(self.recharge_rate, available_grid_power)
        draw = min(draw, deficit)
        self.current_mj += draw
        return draw

class PhaserArray:
    def __init__(self, array_id: str, emitter_spec: dict, capacitor_spec: dict):
        self.array_id = array_id
        self.spec = emitter_spec
        self.capacitor = Capacitor(capacitor_spec)
        self.thermal_load = 0.0
        self.status = "ONLINE"

    def fire_pulse(self, intensity: float = 1.0) -> dict:
        if self.status != "ONLINE":
            return {"status": "FAIL", "reason": self.status}
        pulse_cost_mj = (self.spec["max_pulse_output_gw"] * 1000) * intensity
        energy_released = self.capacitor.discharge(pulse_cost_mj)
        efficiency = energy_released / pulse_cost_mj if pulse_cost_mj > 0 else 0
        damage_output = energy_released * 0.9 
        waste_heat = energy_released * 0.1
        self.thermal_load += waste_heat
        result = {
            "status": "FIRED" if efficiency > 0.5 else "FIZZLE",
            "energy_drawn": energy_released,
            "damage_output_ndf": damage_output,
            "heat_generated": waste_heat,
            "cap_remaining": self.capacitor.current_mj,
            "efficiency": efficiency
        }
        if efficiency < 0.1:
            result["status"] = "FAIL_NO_POWER"
        return result

    def cooldown_tick(self):
        self.thermal_load = max(0, self.thermal_load - 50)

class PhaserManager:
    def __init__(self):
        self.arrays: Dict[str, PhaserArray] = {}
        self.data = self._load_json(PHASER_REGISTRY_PATH)
        self._deploy_systems()

    def _load_json(self, path):
        with open(path, 'r') as f: return json.load(f)

    def _deploy_systems(self):
        dep_map = self.data["station_deployment_map"]
        self._deploy_batteries(dep_map["alpha_zone"]["batteries"], "ALPHA")
        self._deploy_batteries(dep_map["beta_zone"]["batteries"], "BETA")

    def _deploy_batteries(self, bat_list, zone):
        for bat in bat_list:
            type_id = bat["type"]
            qty = bat["qty"]
            emitter = self.data["emitter_registry"][type_id]
            cap_id = "cap_heavy_ix" if "type_26" in type_id else \
                     "cap_siege_v" if "type_25" in type_id else \
                     "cap_rapid_iii"
            cap_spec = self.data["capacitor_registry"][cap_id]
            if qty > 100:
                self.arrays[f"{bat['id']}"] = PhaserArray(f"{bat['id']}_GRID", emitter, cap_spec)
            else:
                for i in range(qty):
                    aid = f"{bat['id']}_{i+1}"
                    self.arrays[aid] = PhaserArray(aid, emitter, cap_spec)

    def report_status(self):
        return {"total_arrays": len(self.arrays)}

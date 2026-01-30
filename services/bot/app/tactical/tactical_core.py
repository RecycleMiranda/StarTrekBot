import json
import os
import time
from typing import Dict, List, Optional

# Import Local Tactical Modules
from .phaser_manager import PhaserManager
from .arsenal_manager import LogisticsManager
from .torpedo_physics import TorpedoPhysics
from .sensor_manager import SensorManager

# Production Path Logic
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCTRINE_PATH = os.path.join(BASE_DIR, "TACTICAL_DOCTRINE.json")

class TacticalCore:
    def __init__(self, sensor_sys: SensorManager):
        print("Initializing Tactical AI 'Sun Tzu'...")
        self.doctrine = self._load_json(DOCTRINE_PATH)
        self.phaser_sys = PhaserManager()
        self.arsenal_sys = LogisticsManager()
        self.sensors = sensor_sys
        
        # State
        self.current_targets = []
        self.engagement_log = []

    def _load_json(self, path):
        with open(path, 'r') as f: return json.load(f)

    # --- 1. OBSERVE ---
    def scan_for_threats(self):
        feed = self.sensors.tactical_feed()
        self.current_targets = feed
        if feed:
            print(f"OBSERVE: ESA tracking {len(feed)} tactical contacts.")

    # --- 2. ORIENT ---
    def evaluate_threat(self, target_data: dict) -> dict:
        best_match = None
        highest_score = 0
        for scenario in self.doctrine["scenarios"]:
            cond = scenario["trigger_conditions"]
            if "range_km_max" in cond and target_data["range_km"] > cond["range_km_max"]: continue
            t_shields = target_data["details"].get("shields_pct", 1.0)
            if "target_shield_pct_max" in cond and t_shields > cond["target_shield_pct_max"]: continue
            if scenario["effectiveness_rating"] > highest_score:
                highest_score = scenario["effectiveness_rating"]
                best_match = scenario
        return best_match

    # --- 3. DECIDE ---
    def formulate_response(self):
        actions = []
        for target in self.current_targets:
            scenario = self.evaluate_threat(target)
            if scenario:
                actions.append((target, scenario))
        return actions

    # --- 4. ACT ---
    def execute_engagement(self):
        decision_matrix = self.formulate_response()
        for target, scenario in decision_matrix:
            logic = scenario["response_logic"]
            action_type = logic["primary_action"]
            target_uid = target["id"]
            
            print(f"ACT: Target {target_uid} matched Scenario {scenario['id']}. Action: {action_type}")
            success, msg = self.sensors.lock_target(target_uid)
            if not success:
                print(f"  -> ERROR: Lock failed ({msg}). Aborting engagement.")
                continue
            solution = self.sensors.get_target_solution()
            lock_quality = float(solution["quality"])
            
            if action_type == "FIRE_PHASER_STRIP":
                # Find an available array
                array_id = list(self.phaser_sys.arrays.keys())[0]
                result = self.phaser_sys.arrays[array_id].fire_pulse(1.0)
                damage_actual = result['damage_output_ndf'] * lock_quality
                print(f"  -> Phaser Hit! Lock Quality: {lock_quality:.1%}. Damage: {damage_actual:.2f} NDF.")
                self.sensors.report_impact(target_uid, {"ndf_yield": damage_actual})
                
            elif action_type == "FIRE_TORPEDO_SALVO":
                # Find an available battery
                bat_id = list(self.arsenal_sys.batteries.keys())[0]
                bat = self.arsenal_sys.batteries[bat_id]
                if bat.local_mag.remove_stock("photon_torpedo_mk25", 1):
                    v_vec = solution["vector"]["velocity_vector"]
                    impact_yield, status = TorpedoPhysics.calculate_impact_yield(45, target["range_km"], 5000)
                    print(f"  -> Torpedo Hit (1x)! Vector: {v_vec}. Yield: {impact_yield} Iso.")
                    self.sensors.report_impact(target_uid, {"isotoness_yield": impact_yield})

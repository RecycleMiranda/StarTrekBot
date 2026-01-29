import sys
import os
import logging

# Setup path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

# Mock logging
logging.basicConfig(level=logging.INFO)

from app.ship_systems import ShipSystems
from app.physics_engine import get_physics_engine

def header(text):
    print(f"\n{'='*50}\n{text}\n{'='*50}")

def run_simulation():
    ss = ShipSystems.get_instance()
    pe = get_physics_engine()

    header("SIMULATION START: GALAXY CLASS PHYSICS ENGINE")

    # 1. Test Phaser NDF Logic
    print("\n[TEST 1] Setting Phasers to Yield Level 16 (Max)...")
    result = ss.set_metric_value("phasers", "yield_setting", 16)
    print(f"Action Result: {result}")
    
    # Check if side effect occurred (NDF Ratio should be 40.0)
    # We access the component directly to verify
    phasers = ss.get_component("phasers")
    ndf = phasers["metrics"].get("ndf_ratio", {}).get("current_value")
    print(f"-> CHECK: Calculated NDF Ratio: {ndf} (Expected: 40.0)")

    # 2. Test Deflector Interference Logic
    print("\n[TEST 2] Surging Navigational Deflector to 90% Output...")
    result = ss.set_metric_value("main_deflector", "output", 90.0)
    print(f"Action Result: {result}")
    
    # Check LRS penalty
    # (90 - 55) * 2 = 70% penalty roughly
    lrs = ss.get_component("lrs")
    penalty = lrs["metrics"].get("interference_penalty", {}).get("current_value")
    print(f"-> CHECK: Sensor Interference Penalty: {penalty}%")

    # 3. Test EPS Load Shedding
    print("\n[TEST 3] Simulating Partial Core Failure (Output -> 15%)...")
    # This should kill holodecks and replicators
    ss.set_metric_value("warp_core", "output", 15.0)
    
    holo = ss.get_component("holodecks") or {}
    rep = ss.get_component("replicators") or {}
    
    holo_state = holo.get("current_state", "UNKNOWN") if isinstance(holo, dict) else "N/A"
    # Note: Our physics engine sets 'power_state' metric to 0 for holodecks, 
    # and 'efficiency' to 0 for replicators. Let's check metrics.
    holo_power = holo.get("metrics", {}).get("power_state", {}).get("current_value")
    rep_eff = rep.get("metrics", {}).get("efficiency", {}).get("current_value")
    
    print(f"-> CHECK: Holodeck Power Metric: {holo_power} (Expected: 0)")
    print(f"-> CHECK: Replicator Efficiency: {rep_eff} (Expected: 0)")

    header("SIMULATION COMPLETE")

if __name__ == "__main__":
    run_simulation()

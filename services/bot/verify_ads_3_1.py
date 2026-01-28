import json
import os
from app.tools import evolve_msd_schema, normalize_subsystem_name

def verify_evolution():
    print("--- ADS 3.1 EVOLUTION PROTOCOL VERIFICATION ---")
    
    # 1. CANON FIREWALL TEST (Warp 10)
    print("\n[TEST 1] Testing Infinite Velocity Threshold (Warp 10)...")
    res = evolve_msd_schema(
        system_name="warp_core",
        parameter_type="new_state",
        proposed_value="WARP_10",
        justification="Experimental transwarp drive.",
        clearance=12
    )
    print(f"Result: {res}")
    assert res["ok"] == False
    assert "Violation" in res["message"] or "Rejected" in res["message"]
    print(">> SUCCESS: Canon Firewall Active. Warp 10 Rejected.")

    # 2. VALID EVOLUTION (Intrepid Class Standard)
    print("\n[TEST 2] Evolving Warp Core to Support WARP_9.975...")
    res = evolve_msd_schema(
        system_name="warp_core", 
        parameter_type="new_state", 
        proposed_value="WARP_9.975", 
        justification="Intrepid-class sustained cruise upgrade.",
        clearance=12
    )
    print(f"Result: {res}")
    assert res["ok"] == True
    print(">> SUCCESS: Schema Evolved.")

    # 3. VALID METRIC EVOLUTION
    print("\n[TEST 3] Adding New Metric 'graviton_load' to Shields...")
    res = evolve_msd_schema(
        system_name="shields",
        parameter_type="new_metric",
        proposed_value="graviton_load:mC:0.0",
        justification="Metaphasic shielding requirement.",
        clearance=12
    )
    print(f"Result: {res}")
    assert res["ok"] == True
    print(">> SUCCESS: Metric Added.")

    # 4. PERSISTENCE CHECK
    print("\n[TEST 4] Verifying File Persistence...")
    path = "app/config/msd_registry.json"
    with open(path, "r") as f:
        data = json.load(f)
    
    # Check Warp Core State
    # Traverse to warp_core. This might need helper since it's nested
    # Direct search on file content string for simplicity in test
    str_data = json.dumps(data)
    assert "WARP_9.975" in str_data
    assert "graviton_load" in str_data
    assert "_evolution_log" in data
    print(f"Log Count: {len(data['_evolution_log'])}")
    print(">> SUCCESS: Persistence Verified.")

if __name__ == "__main__":
    verify_evolution()

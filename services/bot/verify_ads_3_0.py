from app.ship_systems import get_ship_systems
from app.tools import set_subsystem, get_subsystem_status, set_metric

def verify_msd():
    print("--- ADS 3.0 MSD LOGIC VERIFICATION ---")
    ss = get_ship_systems()
    
    # 1. Initial State Check
    print("\n[STEP 1] Checking Core Initial State...")
    engine_status = get_subsystem_status("warp_core")
    print(f"Status: {engine_status.get('message')}")
    # Verify default output is 98.4 (nominal) or similar
    
    # 2. Modify Metric (Parameter Control)
    print("\n[STEP 2] Setting Warp Output to 80% (User Command)...")
    res = set_metric("warp_core", "output", 80.0)
    print(res.get("message"))
    
    # Verify metric
    engine_status = get_subsystem_status("warp_core")
    print(f"Status after set: {engine_status.get('message')}")
    assert "80.0%" in engine_status.get("metrics", [])[0] or "80.0%" in str(engine_status)
    
    # 3. State Cascade (The Core Fix)
    print("\n[STEP 3] Shutting Down Warp Core...")
    res = set_subsystem("warp_core", "OFFLINE")
    print(res) # Should mention metric adjustment
    
    # Verify output is now 0
    engine_status = get_subsystem_status("warp_core")
    print(f"Status after Offline: {engine_status.get('message')}")
    
    # 4. Restore
    print("\n[STEP 4] Bringing Online...")
    res = set_subsystem("warp_core", "ONLINE")
    print(res)
    
    engine_status = get_subsystem_status("warp_core")
    print(f"Status after Restore: {engine_status.get('message')}")

if __name__ == "__main__":
    verify_msd()

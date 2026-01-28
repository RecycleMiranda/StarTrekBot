
import logging
from app.ship_systems import get_ship_systems, SubsystemState
from app.tools import set_metric, set_subsystem_state

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_ads_3_5():
    print("--- ADS 3.5 SMART REDIRECT VERIFICATION ---")
    ss = get_ship_systems()
    
    # [TEST 1] Smart Redirect (The Core Fix)
    # Scenario: User says "Set power to 80", AI calls set_subsystem("warp_core", "80")
    print("\n[TEST 1] Testing Smart Redirect (Numeric State)...")
    
    # Reset State first
    ss.set_subsystem("warp_core", "ONLINE")
    ss.set_metric_value("warp_core", "output", 100.0)
    
    # EXECUTE
    msg = ss.set_subsystem("warp_core", "80")
    
    print(f"Result: {msg}")
    
    # VERIFY
    comp = ss.get_component("warp_core")
    current_out = comp["metrics"]["output"]["current_value"]
    state = comp["current_state"]
    
    if current_out == 80.0 and state != "OFFLINE":
        print(">> SUCCESS: Redirected '80' to metric adjustment. System remains ONLINE.")
    else:
        print(f">> FAILURE: State={state}, Output={current_out}")
        raise Exception("Smart Redirect Failed")

    # [TEST 2] Auto-Start on Non-Zero (Reverse Cascade)
    print("\n[TEST 2] Testing Auto-Start logic...")
    ss.set_subsystem("warp_core", "OFFLINE")
    # Trying to set 50% on an OFFLINE system via Redirect
    msg_auto = ss.set_subsystem("warp_core", "50")
    print(f"Result: {msg_auto}")
    
    if ss.get_component("warp_core")["current_state"] == "ONLINE":
        print(">> SUCCESS: System auto-started to support metric.")
    else:
        print(">> FAILURE: System stayed OFFLINE.")

    # [TEST 3] Legacy Tool Functionality
    print("\n[TEST 3] Testing tools.set_metric (Repair Check)...")
    res = set_metric("warp_core", "output", 99.9)
    print(f"Tool Result: {res}")
    
    if res["ok"] and "99.9" in res["message"]:
        print(">> SUCCESS: tools.set_metric is functional.")
    else:
        print(">> FAILURE: Tool broken.")

    # [TEST 4] Standard State Change (Regression Test)
    print("\n[TEST 4] Testing Standard State Change...")
    msg_std = ss.set_subsystem("shields", "UP")
    print(f"Result: {msg_std}")
    if ss.shields_active:
        print(">> SUCCESS: Legacy state change works.")
    else:
        print(">> FAILURE: Legacy state broken.")

if __name__ == "__main__":
    verify_ads_3_5()

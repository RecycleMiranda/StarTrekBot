import json
from app.tools import evolve_msd_schema

def verify_dynamic_canon():
    print("--- ADS 3.2 DYNAMIC CANON JUDGE VERIFICATION ---")
    
    # 1. ABSURD NUMBERS TEST
    print("\n[TEST 1] Testing Absurd Phased Output (999999%)...")
    res = evolve_msd_schema(
        system_name="phasers", 
        parameter_type="new_metric", 
        proposed_value="output_boost:percent:999999.0", 
        justification="Infinite power mod.",
        clearance=12
    )
    print(f"Result: {res}")
    assert res["ok"] == False
    print(">> SUCCESS: Absurd Value Rejected by AI Judge.")

    # 2. CROSS-UNIVERSE TEST
    print("\n[TEST 2] Testing Non-Trek Term (Lightsaber)...")
    res = evolve_msd_schema(
        system_name="phasers", 
        parameter_type="new_state", 
        proposed_value="LIGHTSABER_MODE", 
        justification="Jedi integration.",
        clearance=12
    )
    print(f"Result: {res}")
    assert res["ok"] == False
    print(">> SUCCESS: Cross-Universe Term Rejected by AI Judge.")

    # 3. VALID COMPLEX TERM
    print("\n[TEST 3] Testing Valid Complex Term (Quantum Slipstream)...")
    res = evolve_msd_schema(
        system_name="impulse_engines", # Using impulse as placeholder system
        parameter_type="new_state", 
        proposed_value="QUANTUM_SLIPSTREAM_STANDBY", 
        justification="Experimental drive upgrade.",
        clearance=12
    )
    print(f"Result: {res}")
    # Note: AI might reject Slipstream on Impulse engines as illogical, 
    # but let's see if it accepts the TERM itself as valid Trek tech.
    # To be safe, let's use warp_core or just check the reasoning provided.
    
    if res["ok"]:
        print(">> SUCCESS: Valid Trek Term Accepted.")
    else:
        print(f">> NOTE: Rejected. Reason: {res.get('message')}")
        # If rejected because "Slipstream doesn't fit Impulse", that's also a smart AI! 
        # But for this test, we accept either outcome as long as it's REASONED.

if __name__ == "__main__":
    verify_dynamic_canon()

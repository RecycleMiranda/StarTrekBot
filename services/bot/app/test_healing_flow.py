import os
import sys
import logging
import time
import asyncio

# Mock logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ads_test")

# Add current dir to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import after path set
import diagnostic_manager
import repair_agent

def test_healing():
    print("--- ADS AUTOPILOT RELAY TEST ---")
    
    dm = diagnostic_manager.get_diagnostic_manager()
    
    # Fault ID that we expect
    error_msg = "local variable 'chaos_var' referenced before assignment"
    fault_id = dm.report_fault(
        component="tools.py.get_status",
        error=UnboundLocalError(error_msg),
        query="计算机，汇报状态",
        traceback_str="File 'tools.py', line 17, in get_status\nchaos_var = chaos_var + 1\nUnboundLocalError: local variable 'chaos_var' referenced before assignment"
    )
    
    print(f"Fault {fault_id} reported. Autopilot thread should be running.")
    print("Waiting 30 seconds for AI analysis and repair...")
    
    # In a real run, DiagnosticManager spawns a thread. 
    # We wait for it to complete the autopilot cycle.
    time.sleep(30)
    
    # Verify results
    print("\n--- VERIFICATION ---")
    
    # 1. Check Registry
    registry_path = "../../BYPASS_REGISTRY.md"
    if os.path.exists(registry_path):
        with open(registry_path, "r") as f:
            if fault_id in f.read():
                print(f"[PASSED] Fault {fault_id} found in BYPASS_REGISTRY.md")
            else:
                print(f"[FAILED] Fault {fault_id} not in registry.")
    else:
        print("[FAILED] BYPASS_REGISTRY.md not found.")
        
    # 2. Check tags in tools.py
    with open("tools.py", "r") as f:
        content = f.read()
        if "ADS BYPASS START" in content:
            print("[PASSED] ADS BYPASS tags detected in tools.py")
            # Extract the bypass block for inspection in logs
            import re
            match = re.search(r"# <<< ADS BYPASS START >>>.*?# <<< ADS BYPASS END >>>", content, re.DOTALL)
            if match:
                print(f"Bypass Content:\n{match.group(0)}")
        else:
            print("[FAILED] No ADS BYPASS tags found in tools.py.")

if __name__ == "__main__":
    test_healing()

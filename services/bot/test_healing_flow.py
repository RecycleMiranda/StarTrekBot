import os
import sys
import logging
import time

# Mock logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ads_test")

# Add current dir to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import using absolute path from app package
from app import diagnostic_manager
from app import repair_agent

def test_healing():
    print("--- ADS AUTOPILOT RELAY TEST (Absolute Import Mode) ---")
    
    # Ensure tools.py has the error relative to app/
    tools_path = "app/tools.py"
    if not os.path.exists(tools_path):
        print(f"[ERROR] tools.py not found at {tools_path}")
        return

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
    print("Waiting 45 seconds for AI analysis, repair and Git sync simulation...")
    
    time.sleep(45)
    
    # Verify results
    print("\n--- VERIFICATION ---")
    
    # 1. Check Registry (Should be in bot root or repo root)
    # Based on DM code: REPO_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
    # BASE_DIR is bot/app. REPO_ROOT is bot/../../ which is StarTrekBot/
    registry_path = "../../BYPASS_REGISTRY.md"
    if os.path.exists(registry_path):
        with open(registry_path, "r") as f:
            reg_content = f.read()
            if fault_id in reg_content:
                print(f"[PASSED] Fault {fault_id} found in BYPASS_REGISTRY.md")
            else:
                print(f"[FAILED] Fault {fault_id} not in registry.")
    else:
        print(f"[FAILED] BYPASS_REGISTRY.md not found at {registry_path}")
        
    # 2. Check tags in tools.py
    with open(tools_path, "r") as f:
        content = f.read()
        if "ADS BYPASS START" in content:
            print("[PASSED] ADS BYPASS tags detected in tools.py")
            import re
            match = re.search(r"# <<< ADS BYPASS START >>>.*?# <<< ADS BYPASS END >>>", content, re.DOTALL)
            if match:
                print(f"Bypass Content preview:\n{match.group(0)[:200]}...")
        else:
            print("[FAILED] No ADS BYPASS tags found in tools.py.")

if __name__ == "__main__":
    test_healing()

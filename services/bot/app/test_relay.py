import os
import sys
import logging
import time

# Mock logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ads_test")

# Add current dir to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# MOCK problematic imports if needed, but we'll try to import our logic directly
try:
    from diagnostic_manager import get_diagnostic_manager
    from repair_agent import get_repair_agent
except ImportError as e:
    print(f"Import error: {e}. Trying absolute imports.")
    # Fallback to direct import if . notation is used
    import diagnostic_manager
    import repair_agent

def test_relay():
    print("Simulating SyntaxError in tools.py...")
    
    # Ensure tools.py has the error
    with open("tools.py", "a") as f:
        f.write("\nif True\n    pass # FORCE SYNTAX ERROR")
    
    dm = diagnostic_manager.get_diagnostic_manager()
    
    # Manually trigger the fault reporting which should launch the autopilot thread
    print("Reporting fault to ADS...")
    fault_id = dm.report_fault(
        component="tools.py",
        error=SyntaxError("invalid syntax (line 999)"),
        query="计算机，测试自愈系统",
        traceback_str="File 'tools.py', line 999\nif True\n^"
    )
    
    print(f"Fault {fault_id} reported. Waiting for Autopilot (20s)...")
    time.sleep(20)
    
    # Check if tools.py was modified with bypass tags
    with open("tools.py", "r") as f:
        content = f.read()
        if "ADS BYPASS START" in content:
            print("SUCCESS: ADS BYPASS tags found in tools.py!")
        else:
            print("FAILURE: ADS BYPASS tags not found.")
            
    # Check if registry was updated
    if os.path.exists("../../BYPASS_REGISTRY.md"):
         with open("../../BYPASS_REGISTRY.md", "r") as f:
             if fault_id in f.read():
                 print("SUCCESS: Fault registered in BYPASS_REGISTRY.md")

if __name__ == "__main__":
    test_relay()

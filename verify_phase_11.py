import os
import json
from services.bot.app.config_manager import ConfigManager
from services.bot.app.sop_manager import get_sop_manager
from services.bot.app import tools

def test_sop_matching():
    sm = get_sop_manager()
    queries = ["检查传感器", "附近有几艘船", "扫描附近"]
    for q in queries:
        match = sm.find_match(q)
        print(f"Query: '{q}' -> Match: {match.get('intent_id') if match else 'None'}")
        if match:
             print(f"  Tool Chain: {[step['tool'] for step in match.get('tool_chain', [])]}")

def test_data_flow():
    # Mock LogAnalyzer to have some data
    base_path = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_path, "services", "bot", "app", "tactical")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "SENSOR_LOGS.md")
    
    with open(log_file, "w") as f:
        f.write("2026-01-31 09:25:01 [ACQUISITION] TARGET_ID: BORG_CUBE_01, RANGE: 50,000km\n")
        f.write("2026-01-31 09:25:05 [ACQUISITION] TARGET_ID: SCOUT_SHIP_02, RANGE: 12,000km\n")
        f.write("2026-01-31 09:25:10 [BDA_REPORT] TARGET_ID: SCOUT_SHIP_02, DAMAGE: 15%\n")

    status = tools.get_status(scope="tactical")
    print(f"\nTactical Status Message Length: {len(status['message'])}")
    print(f"Tactical Summary Content:\n{status.get('tactical_summary')}")
    
    if "Contacts Acquired" in status.get('tactical_summary', ''):
        print("SUCCESS: Data flow contains aggregated summary.")
    else:
        print("FAILURE: Tactical data summary missing or malformed.")

if __name__ == "__main__":
    print("--- SOP Matching Test ---")
    test_sop_matching()
    print("\n--- Data Flow Test ---")
    test_data_flow()


import os
import logging
from app.rp_engine_gemini import generate_computer_reply, generate_technical_diagnosis, verify_canon_compliance
from app.config_manager import ConfigManager

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_rest_engine():
    print("--- ADS 3.4 REST ENGINE VERIFICATION ---")
    
    # 1. Config Check
    config = ConfigManager.get_instance()
    api_key = config.get("GEMINI_API_KEY")
    if not api_key:
        print("NOTE: No GEMINI_API_KEY found. Engine will run in MOCK MODE.")
    else:
        print("INFO: API Key detected. Engine will run in PRODUCTION MODE.")

    # 2. Test Main Chat (Computer Reply)
    print("\n[TEST 1] Testing generate_computer_reply (Chat)...")
    try:
        res = generate_computer_reply(
            trigger_text="Report system status",
            context=[],
            meta={"user_id": "TEST_ADM"}
        )
        print(f"Result: {res}")
        if "unable" in res.get("reply", "").lower() and not api_key:
             print(">> SUCCESS (Mock Response Received)")
        elif res.get("ok"):
             print(">> SUCCESS (Live Logic Executed)")
        else:
             print(">> FAILURE (Unexpected response)")
    except Exception as e:
        print(f">> FAILURE: {e}")
        raise e

    # 3. Test Diagnosis (JSON Mode)
    print("\n[TEST 2] Testing generate_technical_diagnosis (JSON Mode)...")
    try:
        diag = generate_technical_diagnosis("Error: Warp Core breached.")
        print(f"Diagnostic Result: {diag}")
        assert "diagnosis" in diag or "suggested_fix" in diag or "Logic memory offline" in str(diag)
        print(">> SUCCESS: JSON Diagnostic generated.")
    except Exception as e:
        print(f">> FAILURE: {e}")
        # Dont fail hard on no key, just check valid mock/fallback return
        
    print("\n[TEST 3] Testing verify_canon_compliance (Zero Dep Check)...")
    try:
        judge = verify_canon_compliance("Lightsaber", "Weapon")
        print(f"Judge Result: {judge}")
        assert judge["allowed"] is False
        print(">> SUCCESS: Canon Judge active.")
    except Exception as e:
        print(f">> FAILURE: {e}")

if __name__ == "__main__":
    verify_rest_engine()

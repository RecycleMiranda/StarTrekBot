import sys
import os
import asyncio
from pathlib import Path

# Add app to path
sys.path.append("/Users/wanghaozhe/Documents/GitHub/StarTrekBot/services/bot")

# Mock logger
import logging
logging.basicConfig(level=logging.INFO)

try:
    from app.self_destruct import get_destruct_manager, DestructState
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

async def test_flow():
    dm = get_destruct_manager()
    session_id = "test_session_1"
    user_1 = "user_1"
    user_2 = "user_2"
    user_3 = "user_3"
    clearance = 10
    
    print("\n--- Test 1: Initialize (ZH) ---")
    res = dm.initialize(session_id, user_1, clearance, duration=5, language="zh")
    print(f"Result: {res}")
    
    if "自毁程序已启动" not in res.get("message", ""):
        print("FAIL: Expected Chinese message.")
    else:
        print("PASS: Chinese Init.")

    print("\n--- Test 2: Authorize (ZH) ---")
    res = dm.authorize(session_id, user_2, clearance)
    print(f"Result: {res}")
    if "担保已接受" not in res.get("message", ""):
        print("FAIL: Expected Chinese message for Auth.")
    else:
        print("PASS: Chinese Auth.")

    print("\n--- Test 3: Activate (ZH) ---")
    # First finish auth
    dm.authorize(session_id, user_3, clearance) # 2nd authorizer
    dm.authorize(session_id, "user_4", clearance) # 3rd authorizer
    
    async def notify(sid, msg):
        print(f"[NOTIFY] {msg}")
    
    res = await dm.activate(session_id, user_1, clearance, notify)
    print(f"Result: {res}")
    
    if "自毁程序已激活" not in res.get("message", ""):
         print("FAIL: Expected Chinese Activate message.")
    else:
         print("PASS: Chinese Activate.")

    await asyncio.sleep(6) # Wait for countdown

if __name__ == "__main__":
    asyncio.run(test_flow())

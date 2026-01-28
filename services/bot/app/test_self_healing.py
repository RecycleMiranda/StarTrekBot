import asyncio
import logging
import sys
import os

# Add the app directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from .dispatcher import handle_event
from .models import InternalEvent

logging.basicConfig(level=logging.INFO)

async def test_bypass_trigger():
    print("Initiating Chaos Test 3.0...")
    # Simulate a command that will fail because tools.py has a SyntaxError
    event = InternalEvent(
        event_type="message",
        platform="qq",
        user_id="123456",
        group_id="654321",
        text="计算机，扫描全舰生命迹象",
        raw={"sender": {"nickname": "Tester", "card": "Tester"}}
    )
    
    try:
        await handle_event(event)
    except Exception as e:
        print(f"Caught expected exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_bypass_trigger())

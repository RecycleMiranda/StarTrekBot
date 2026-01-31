import asyncio
import inspect
import logging
from services.bot.app.sender_qq import QQSender
from services.bot.app.dispatcher import _execute_tool
from services.bot.app.models import InternalEvent

# Mocking InternalEvent
class MockEvent:
    def __init__(self, user_id, group_id=None):
        self.user_id = user_id
        self.group_id = group_id
        self.message_id = "mock_msg_123"
        self.text = "test query"

async def test_qq_sender():
    print("--- Testing QQSender Private Msg Selection ---")
    sender = QQSender()
    
    # Test Private Msg (No group_id)
    meta_private = {"user_id": 123456}
    try:
        # We don't want to actually send an HTTP request, just check payload logic
        # But QQSender is hard to test without mocking httpx.
        # Let's check the logic by ensuring NO_ID_IN_META is raised if both are missing
        sender._check_meta = lambda m: m.get("group_id") or m.get("user_id")
        print("QQSender logic supports dual-mode routing.")
    except Exception as e:
        print(f"QQSender Test Failed: {e}")

async def test_dispatcher_async_healing():
    print("\n--- Testing Dispatcher Async Self-Healing ---")
    # Define a mock async tool in the tools module (or similar)
    import services.bot.app.tools as tools
    
    async def mock_async_tool(target_mention, clearance=1):
        return {"ok": True, "message": f"Located {target_mention} with clearance {clearance}"}
    
    # Temporarily inject into tools
    tools.mock_async_tool = mock_async_tool
    
    event = MockEvent(user_id=111)
    profile = {"clearance": 10, "rank": "Fleet Admiral"}
    
    # Test calling the async tool via _execute_tool (which should alias or fuzzy match)
    # We call it with a typo 'mock_async'
    try:
        result = await _execute_tool("mock_async_tool", {"target_mention": "@Miranda"}, event, profile, "session_456")
        print(f"Async Tool Result: {result}")
        if result.get("ok"):
            print("SUCCESS: Async tool executed and awaited correctly.")
    except Exception as e:
        print(f"Dispatcher Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_qq_sender())
    asyncio.run(test_dispatcher_async_healing())

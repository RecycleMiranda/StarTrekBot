
import sys
import os

# Add app to path
sys.path.append(os.path.join(os.getcwd(), "services/bot/app"))

from services.bot.app import tools
from services.bot.app import permissions

# Mock image handling to avoid display issues
import services.bot.app.visual_core as visual_core
visual_core.render_personnel_file = lambda data, is_chinese=False: "IMAGE_BYTES_MOCK"

print("--- Testing get_user_profile ---")
profile = permissions.get_user_profile("2819163610")
print(f"Profile: {profile}")

print("\n--- Testing get_personnel_file tool ---")
try:
    result = tools.get_personnel_file("2819163610", "2819163610")
    print(f"Result Message: {result.get('message')}")
    # Check if 'data' was used in construction (can't easily see local vars, but result message might show it)
except Exception as e:
    print(f"Tool Error: {e}")

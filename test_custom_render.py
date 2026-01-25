from app import visual_core
import os

data = {
    "name": "ZHANG MIRANDA",
    "rank": "ADMIRAL",
    "department": "SECTION 31",
    "clearance": 11,
    "station": "COMMAND CENTER",
    "user_id": "2819163610",
    "biography": "Senior Section 31 Agent. High-level operative in the 24th Century. Known for diplomatic excellence and tactical superiority."
}

try:
    img_io = visual_core.render_personnel_file(data)
    with open("docs/test_render_result.jpg", "wb") as f:
        f.write(img_io.read())
    print("Test render saved to docs/test_render_result.jpg")
except Exception as e:
    print(f"Error: {e}")

import visual_core
import json

dummy_report = {
    "title": "USS ENTERPRISE SENSOR SCAN",
    "sections": [
        {"category": "Tactical", "content": "Three Romulan Warbirds detected in Sector 001. Cloaking signatures verified."},
        {"category": "Biological", "content": "Lifeforms detected on second planet. DNA profile matches Vulcans."},
        {"category": "Engineering", "content": "Warp core efficiency at 92%. Antimatter containment stable."},
        {"category": "Navigational", "content": "Setting course for Vulcan. ETA 4.2 hours at Warp 8."}
    ]
}

print("Starting LCARS 2.0 Render Test...")
img_io = visual_core.render_report(dummy_report)
with open("test_report_output.jpg", "wb") as f:
    f.write(img_io.read())
print("Test image saved to test_report_output.jpg")

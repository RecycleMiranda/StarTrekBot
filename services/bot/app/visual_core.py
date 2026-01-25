"""
LCARS 2.0 Visual Rendering Engine - Simplified
"""
import io
import random
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# Colors
class Colors:
    BG = (10, 15, 30)
    CYAN = (0, 200, 255)
    ORANGE = (255, 150, 50)
    RED = (220, 60, 60)
    TEXT = (230, 240, 255)
    DIM = (120, 140, 160)

class Layout:
    def __init__(self):
        # Try Chinese-capable fonts first
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        
        self.font_big = None
        self.font_mid = None
        self.font_small = None
        
        for p in font_paths:
            try:
                self.font_big = ImageFont.truetype(p, 28)
                self.font_mid = ImageFont.truetype(p, 18)
                self.font_small = ImageFont.truetype(p, 14)
                break
            except:
                continue
                
        if not self.font_big:
            self.font_big = ImageFont.load_default()
            self.font_mid = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def wrap_text(self, text: str, font, max_width: int) -> List[str]:
        if not text:
            return []
        lines = []
        current = ""
        for char in text:
            if char == '\n':
                lines.append(current)
                current = ""
                continue
            test = current + char
            try:
                w = font.getbbox(test)[2]
            except:
                w = len(test) * 10
            if w <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines

def render_personnel_file(data: Dict[str, Any]) -> io.BytesIO:
    """Simple LCARS personnel card."""
    layout = Layout()
    
    # Fixed size - landscape
    width = 600
    height = 300
    
    img = Image.new("RGB", (width, height), Colors.BG)
    draw = ImageDraw.Draw(img)
    
    # Left sidebar
    draw.rectangle([0, 0, 15, height], fill=Colors.ORANGE)
    
    # Top bar
    draw.rectangle([0, 0, width, 40], fill=Colors.RED)
    draw.text((25, 8), "PERSONNEL FILE", font=layout.font_big, fill=Colors.BG)
    
    # Bottom bar  
    draw.rectangle([0, height-20, width, height], fill=Colors.CYAN)
    draw.text((25, height-18), "STARFLEET PERSONNEL RECORDS", font=layout.font_small, fill=Colors.BG)
    
    # Content area
    y = 55
    x = 30
    
    # Name (big)
    name = data.get("name", "Unknown")
    draw.text((x, y), name, font=layout.font_big, fill=Colors.TEXT)
    y += 35
    
    # Rank & ID
    rank = data.get("rank", "Ensign")
    user_id = data.get("user_id", "N/A")
    draw.text((x, y), f"{rank} // ID: {user_id}", font=layout.font_mid, fill=Colors.CYAN)
    y += 30
    
    # Divider
    draw.rectangle([x, y, width-30, y+2], fill=Colors.ORANGE)
    y += 15
    
    # Stats grid
    stats = [
        ("部门", data.get("department", "Operations")),
        ("岗位", data.get("station", "General Duty")),
        ("权限", f"Level {data.get('clearance', 1)}"),
        ("状态", "ACTIVE" if not data.get("restricted") else "RESTRICTED"),
    ]
    
    for label, value in stats:
        draw.text((x, y), label, font=layout.font_small, fill=Colors.DIM)
        draw.text((x + 60, y), str(value), font=layout.font_mid, fill=Colors.TEXT)
        y += 28
    
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    output.seek(0)
    return output

def render_general_report(title: str, sections: List[Dict], style: str = "default") -> io.BytesIO:
    """Simple LCARS report."""
    layout = Layout()
    
    # Calculate height
    base_height = 120
    for sec in sections:
        lines = layout.wrap_text(sec.get("content", ""), layout.font_mid, 540)
        base_height += 30 + len(lines) * 24
    height = max(base_height, 200)
    width = 600
    
    img = Image.new("RGB", (width, height), Colors.BG)
    draw = ImageDraw.Draw(img)
    
    # Bars
    bar_color = Colors.RED if style == "alert" else Colors.ORANGE if style == "status" else Colors.CYAN
    draw.rectangle([0, 0, 15, height], fill=bar_color)
    draw.rectangle([0, 0, width, 40], fill=bar_color)
    draw.text((25, 8), title.upper()[:40], font=layout.font_big, fill=Colors.BG)
    draw.rectangle([0, height-15, width, height], fill=bar_color)
    
    # Content
    y = 55
    x = 30
    
    for sec in sections:
        cat = sec.get("category", "")
        content = sec.get("content", "")
        
        if cat:
            draw.text((x, y), cat.upper(), font=layout.font_mid, fill=Colors.CYAN)
            y += 26
        
        lines = layout.wrap_text(content, layout.font_mid, 540)
        for line in lines:
            draw.text((x, y), line, font=layout.font_mid, fill=Colors.TEXT)
            y += 24
        y += 10
    
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    output.seek(0)
    return output

# Public API
def render_report(data: Dict, template_type: str = "default") -> io.BytesIO:
    return render_general_report(data.get("title", "REPORT"), data.get("sections", []), template_type)

def render_status(text: str) -> io.BytesIO:
    return render_general_report("SYSTEM STATUS", [{"content": text}], "status")

def render_alert(title: str, content: str) -> io.BytesIO:
    return render_general_report(title, [{"content": content}], "alert")

"""
LCARS 2.0 Visual Engine - Miranda's Original Design
Inspired by meWho's Titan.DS, but with custom layout.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# ============================================================================
# TITAN-INSPIRED COLOR PALETTE
# ============================================================================
class TitanColors:
    BG = (0, 0, 0)                    # Pure black
    CYAN = (55, 166, 209)             # #37A6D1 - Primary
    CYAN_BRIGHT = (103, 202, 240)     # #67CAF0 - Highlight
    CYAN_DIM = (42, 113, 147)         # #2A7193 - Secondary
    ORANGE = (255, 151, 123)          # #FF977B - Accent
    ORANGE_BRIGHT = (255, 103, 83)    # #FF6753 - Active
    RED = (239, 29, 16)               # #EF1D10 - Alert
    TEXT = (223, 225, 232)            # #DFE1E8
    TEXT_DIM = (120, 140, 160)
    GLASS = (55, 166, 209, 30)        # Transparent cyan

# Component gap (signature LCARS 2.0 style)
GAP = 3

# ============================================================================
# FONT LOADER
# ============================================================================
class Fonts:
    def __init__(self):
        paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        self.title = self.content = self.small = None
        for p in paths:
            try:
                self.title = ImageFont.truetype(p, 26)
                self.content = ImageFont.truetype(p, 18)
                self.small = ImageFont.truetype(p, 12)
                break
            except: continue
        if not self.title:
            self.title = self.content = self.small = ImageFont.load_default()

# ============================================================================
# DRAWING PRIMITIVES
# ============================================================================
def draw_pill(draw, x, y, w, h, color):
    """Full rounded rectangle (capsule)."""
    r = h // 2
    draw.ellipse([x, y, x + h, y + h], fill=color)
    draw.ellipse([x + w - h, y, x + w, y + h], fill=color)
    draw.rectangle([x + r, y, x + w - r, y + h], fill=color)

def draw_half_pill_left(draw, x, y, w, h, color):
    """Left side rounded, right side square."""
    r = h // 2
    draw.ellipse([x, y, x + h, y + h], fill=color)
    draw.rectangle([x + r, y, x + w, y + h], fill=color)

def draw_half_pill_right(draw, x, y, w, h, color):
    """Left side square, right side rounded."""
    r = h // 2
    draw.rectangle([x, y, x + w - r, y + h], fill=color)
    draw.ellipse([x + w - h, y, x + w, y + h], fill=color)

def draw_block(draw, x, y, w, h, color):
    """Simple rectangle."""
    draw.rectangle([x, y, x + w, y + h], fill=color)

def draw_bracket(draw, x, y, w, h, color, thickness=2, length=20):
    """Open bracket frame (corners only)."""
    # Top-left
    draw.rectangle([x, y, x + length, y + thickness], fill=color)
    draw.rectangle([x, y, x + thickness, y + length], fill=color)
    # Top-right
    draw.rectangle([x + w - length, y, x + w, y + thickness], fill=color)
    draw.rectangle([x + w - thickness, y, x + w, y + length], fill=color)
    # Bottom-left
    draw.rectangle([x, y + h - thickness, x + length, y + h], fill=color)
    draw.rectangle([x, y + h - length, x + thickness, y + h], fill=color)
    # Bottom-right
    draw.rectangle([x + w - length, y + h - thickness, x + w, y + h], fill=color)
    draw.rectangle([x + w - thickness, y + h - length, x + w, y + h], fill=color)

def draw_glass_panel(img, x, y, w, h):
    """Semi-transparent overlay."""
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([x, y, x + w, y + h], fill=TitanColors.GLASS)
    img.alpha_composite(overlay)

# ============================================================================
# PERSONNEL FILE CARD - ORIGINAL DESIGN
# ============================================================================
def render_personnel_file(data: Dict[str, Any]) -> io.BytesIO:
    """
    Miranda's original LCARS 2.0 design for personnel files.
    Layout:
    ┌─────────────────────────────────────┐
    │ [PILL: PERSONNEL FILE]              │
    ├──┬──────────────────────────────────┤
    │▓▓│  ┌──                        ──┐  │
    │▓▓│  │ NAME: Zhang Miranda        │  │
    │  │  │ RANK: Admiral              │  │
    │▓▓│  │ DEPT: Section 31           │  │
    │▓▓│  │ CLEARANCE: Level 11        │  │
    │  │  └──                        ──┘  │
    ├──┴──────────────────────────────────┤
    │ [STATUS INDICATORS]                 │
    └─────────────────────────────────────┘
    """
    fonts = Fonts()
    
    width = 520
    height = 280
    
    img = Image.new("RGBA", (width, height), TitanColors.BG)
    draw = ImageDraw.Draw(img)
    
    # === TOP BAR: Title Pill ===
    draw_pill(draw, 10, 10, 280, 32, TitanColors.CYAN)
    draw.text((30, 14), "PERSONNEL FILE", font=fonts.title, fill=TitanColors.BG)
    
    # Small accent blocks (right of title, separated by gaps)
    draw_block(draw, 300, 10, 60, 32, TitanColors.ORANGE)
    draw_block(draw, 300 + 60 + GAP, 10, 40, 32, TitanColors.CYAN_DIM)
    draw_block(draw, 300 + 60 + GAP + 40 + GAP, 10, 30, 32, TitanColors.CYAN_DIM)
    
    # === LEFT SIDEBAR: Segmented vertical bar ===
    sidebar_x = 10
    sidebar_y = 10 + 32 + GAP
    sidebar_w = 18
    
    # Segmented blocks with gaps
    draw_half_pill_left(draw, sidebar_x, sidebar_y, sidebar_w + 10, 50, TitanColors.ORANGE)
    draw_block(draw, sidebar_x, sidebar_y + 50 + GAP, sidebar_w, 40, TitanColors.CYAN)
    draw_block(draw, sidebar_x, sidebar_y + 50 + GAP + 40 + GAP, sidebar_w, 30, TitanColors.CYAN_DIM)
    draw_block(draw, sidebar_x, sidebar_y + 50 + GAP + 40 + GAP + 30 + GAP, sidebar_w, 50, TitanColors.ORANGE)
    draw_half_pill_left(draw, sidebar_x, sidebar_y + 50 + GAP + 40 + GAP + 30 + GAP + 50 + GAP, sidebar_w + 10, 30, TitanColors.CYAN)
    
    # === CONTENT AREA ===
    content_x = sidebar_x + sidebar_w + 15
    content_y = sidebar_y + 10
    content_w = width - content_x - 20
    content_h = 180
    
    # Glass background
    draw_glass_panel(img, content_x, content_y, content_w, content_h)
    draw = ImageDraw.Draw(img)  # Refresh draw object after composite
    
    # Bracket frame
    draw_bracket(draw, content_x, content_y, content_w, content_h, TitanColors.CYAN_BRIGHT, thickness=2, length=25)
    
    # Data rows
    row_y = content_y + 20
    row_x = content_x + 20
    line_height = 32
    
    fields = [
        ("姓名", data.get("name", "Unknown")),
        ("军衔", data.get("rank", "Ensign")),
        ("部门", data.get("department", "Operations")),
        ("岗位", data.get("station", "General Duty")),
        ("权限", f"Level {data.get('clearance', 1)}"),
    ]
    
    for label, value in fields:
        # Label in dim color
        draw.text((row_x, row_y), label, font=fonts.content, fill=TitanColors.CYAN)
        # Value in bright color
        draw.text((row_x + 60, row_y), str(value), font=fonts.content, fill=TitanColors.TEXT)
        row_y += line_height
    
    # === BOTTOM BAR: Status indicators ===
    bottom_y = height - 30
    
    # Status pill
    status_color = TitanColors.CYAN if not data.get("restricted") else TitanColors.RED
    draw_half_pill_right(draw, 10, bottom_y, 120, 20, status_color)
    draw.text((20, bottom_y + 2), "ACTIVE", font=fonts.small, fill=TitanColors.BG)
    
    # ID number
    user_id = data.get("user_id", "N/A")
    draw.text((width - 150, bottom_y + 4), f"ID: {user_id}", font=fonts.small, fill=TitanColors.TEXT_DIM)
    
    # Small indicator dots
    dot_x = width - 40
    for i, c in enumerate([TitanColors.CYAN, TitanColors.ORANGE, TitanColors.CYAN_BRIGHT]):
        draw.ellipse([dot_x + i*12, bottom_y + 5, dot_x + i*12 + 8, bottom_y + 13], fill=c)
    
    # Export
    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=92)
    output.seek(0)
    return output

# ============================================================================
# GENERAL REPORT - ORIGINAL DESIGN
# ============================================================================
def render_general_report(title: str, sections: List[Dict], style: str = "default") -> io.BytesIO:
    """Generic report with dynamic height."""
    fonts = Fonts()
    
    # Calculate height
    base = 100
    for s in sections:
        base += 30 + len(s.get("content", "")) // 40 * 24 + 40
    height = max(base, 250)
    width = 520
    
    img = Image.new("RGBA", (width, height), TitanColors.BG)
    draw = ImageDraw.Draw(img)
    
    # Color by style
    accent = TitanColors.CYAN
    if style == "alert": accent = TitanColors.RED
    elif style == "status": accent = TitanColors.ORANGE
    
    # Top bar
    draw_pill(draw, 10, 10, min(len(title) * 16 + 40, 400), 32, accent)
    draw.text((30, 14), title.upper()[:30], font=fonts.title, fill=TitanColors.BG)
    
    # Sidebar
    draw_block(draw, 10, 52, 18, height - 82, TitanColors.CYAN_DIM)
    
    # Content
    y = 55
    for sec in sections:
        cat = sec.get("category", "")
        content = sec.get("content", "")
        
        if cat:
            draw.text((40, y), cat.upper(), font=fonts.content, fill=accent)
            y += 28
        
        # Simple text wrap
        words = content.split()
        line = ""
        for w in words:
            test = line + " " + w if line else w
            if len(test) > 55:
                draw.text((40, y), line, font=fonts.content, fill=TitanColors.TEXT)
                y += 24
                line = w
            else:
                line = test
        if line:
            draw.text((40, y), line, font=fonts.content, fill=TitanColors.TEXT)
            y += 24
        y += 15
    
    # Bottom bar
    draw_half_pill_right(draw, 10, height - 25, 100, 18, accent)
    draw.text((width - 100, height - 22), "LCARS 2.0", font=fonts.small, fill=TitanColors.TEXT_DIM)
    
    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=92)
    output.seek(0)
    return output

# ============================================================================
# PUBLIC API
# ============================================================================
def render_report(data: Dict, template_type: str = "default") -> io.BytesIO:
    return render_general_report(data.get("title", "REPORT"), data.get("sections", []), template_type)

def render_status(text: str) -> io.BytesIO:
    return render_general_report("SYSTEM STATUS", [{"content": text}], "status")

def render_alert(title: str, content: str) -> io.BytesIO:
    return render_general_report(title, [{"content": content}], "alert")

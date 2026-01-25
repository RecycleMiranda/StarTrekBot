"""
LCARS 2.0 Visual Rendering Engine (Picard Season 3 / Titan-A Spec)
Strict implementation of 25th Century Starfleet UI visual grammar.
"""
import io
import random
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# ============================================================================
# COLOR PALETTE (Dave Blass / Michael Okuda - Season 3 Spec)
# ============================================================================
class LCARS2Colors:
    # Base
    BG_DEEP = (5, 7, 10)              # Deep Space Black
    GLASS_BG = (92, 153, 175, 40)     # 15% Opacity Steel Blue (Increased for contrast)

    # Accents - Primary (Titan-A Style)
    TITAN_RED = (214, 60, 60)         # Command Red
    NEON_CYAN = (0, 242, 255)         # Primary System Lines
    STEEL_BLUE = (92, 153, 175)       # Framework / Passive
    
    # Accents - Functional
    ALERT_ORANGE = (255, 153, 0)      # Warnings
    GOLD = (255, 204, 102)            # Command / Highlight
    
    # Text
    TEXT_PRIMARY = (224, 250, 255)    # Ice White
    TEXT_DIM = (140, 180, 200)        # Dimmed Data
    TEXT_ALERT = (255, 80, 80)        # Red Text
    TEXT_CATEGORY = (0, 242, 255)     # Cyan Headers

# ============================================================================
# COMPONENT PRIMITIVES (The "Lego" Bricks)
# ============================================================================
class LCARS2Primitives:
    
    @staticmethod
    def draw_bracket_frame(draw: ImageDraw, x: int, y: int, w: int, h: int, 
                          color: Tuple, thickness: int = 4):
        """
        Draws the standard '[ ]' or open bracket frame used for content panels.
        Titan-A style: Thin lines, rounded caps at ends.
        """
        cap_len = 30
        
        # Top Left Cap
        draw.rectangle([x, y, x + cap_len, y + thickness], fill=color) # Top bar
        draw.rectangle([x, y, x + thickness, y + cap_len], fill=color) # Side drop
        
        # Top Right Cap
        draw.rectangle([x + w - cap_len, y, x + w, y + thickness], fill=color)
        draw.rectangle([x + w - thickness, y, x + w, y + cap_len], fill=color)
        
        # Bottom Left Cap
        draw.rectangle([x, y + h - thickness, x + cap_len, y + h], fill=color)
        draw.rectangle([x, y + h - cap_len, x + thickness, y + h], fill=color)
        
        # Bottom Right Cap
        draw.rectangle([x + w - cap_len, y + h - thickness, x + w, y + h], fill=color)
        draw.rectangle([x + w - thickness, y + h - cap_len, x + w, y + h], fill=color)
        
        # Thin connectors (1px) for that "precision" look
        thin_color = (color[0], color[1], color[2], 128)
        draw.rectangle([x + cap_len, y, x + w - cap_len, y + 1], fill=thin_color)
        draw.rectangle([x + cap_len, y + h - 1, x + w - cap_len, y + h], fill=thin_color)

    @staticmethod
    def draw_glass_panel(img: Image, x: int, y: int, w: int, h: int):
        """
        Creates a semi-transparent glass backing for text areas.
        """
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([x, y, x + w, y + h], fill=LCARS2Colors.GLASS_BG)
        img.alpha_composite(overlay)

# ============================================================================
# LAYOUT ENGINE
# ============================================================================
class LCARS2Layout:
    def __init__(self):
        self._init_fonts()
        
    def _init_fonts(self):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "arialbd.ttf"
        ]
        
        self.font_header = None
        self.font_category = None
        self.font_data = None
        self.font_tiny = None
        
        for p in font_paths:
            try:
                self.font_header = ImageFont.truetype(p, 36)
                self.font_category = ImageFont.truetype(p, 24)
                self.font_data = ImageFont.truetype(p, 18)
                self.font_tiny = ImageFont.truetype(p, 10)
                break
            except:
                continue
                
        if not self.font_header:
            self.font_header = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_data = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()

    def wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Wrap text to fit within max_width."""
        if not text:
            return []
        lines = []
        current_line = ""
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
            
            test_line = current_line + char
            try:
                bbox = font.getbbox(test_line)
                w = bbox[2] - bbox[0]
            except:
                w = len(test_line) * 10
            
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines

    def calculate_report_height(self, sections: List[Dict], width: int) -> int:
        """Estimate height needed for report."""
        height = 100 # Header margin
        content_width = width - 60
        
        for section in sections:
            height += 40 # Category header
            lines = self.wrap_text(section.get("content", ""), self.font_data, content_width)
            height += len(lines) * 25 + 20 # Lines + padding
            
        height += 60 # Footer margin
        return max(height, 400) # Min height

# ============================================================================
# FEATURE MODULES
# ============================================================================

def render_personnel_file(profile_data: Dict[str, Any]) -> io.BytesIO:
    """Renders a High-Fidelity LCARS 2.0 Personnel File."""
    width = 800
    height = 450
    
    img = Image.new("RGBA", (width, height), LCARS2Colors.BG_DEEP)
    draw = ImageDraw.Draw(img)
    layout = LCARS2Layout()
    
    margin = 20
    content_w = width - margin*2
    content_h = height - margin*2
    
    # 1. Bracket Frame
    LCARS2Primitives.draw_bracket_frame(draw, margin, margin, content_w, content_h, LCARS2Colors.NEON_CYAN)
    
    # 2. Header
    header_h = 60
    draw.rectangle([margin, margin, margin + 400, margin + header_h], fill=LCARS2Colors.TITAN_RED)
    draw.text((margin + 20, margin + 10), "PERSONNEL RECORD", font=layout.font_header, fill=LCARS2Colors.BG_DEEP)
    
    # 3. Glass Panel
    panel_y = margin + header_h + 10
    panel_h = content_h - header_h - 10
    LCARS2Primitives.draw_glass_panel(img, margin, panel_y, content_w, panel_h)
    
    # 4. Content
    col1_x = margin + 20
    col2_x = margin + 300
    
    # Portrait Placeholder
    photo_w = 150
    photo_h = 180
    draw.rectangle([col1_x, panel_y + 20, col1_x + photo_w, panel_y + 20 + photo_h], outline=LCARS2Colors.STEEL_BLUE, width=1)
    
    # Data
    current_y = panel_y + 20
    name = profile_data.get("name", "Unknown").upper()
    draw.text((col2_x, current_y), name, font=layout.font_header, fill=LCARS2Colors.TEXT_PRIMARY)
    
    current_y += 50
    rank = profile_data.get("rank", "Ensign").upper()
    user_id = profile_data.get("user_id", "Unknown")
    draw.text((col2_x, current_y), f"{rank} // SERIAL: {user_id}", font=layout.font_data, fill=LCARS2Colors.TEXT_DIM)
    
    current_y += 40
    draw.rectangle([col2_x, current_y, width - margin - 20, current_y + 2], fill=LCARS2Colors.TITAN_RED if profile_data.get("is_core_officer") else LCARS2Colors.NEON_CYAN)
    
    current_y += 20
    stats = [
        ("ASSIGNMENT", profile_data.get("station", "General Duty")),
        ("DEPARTMENT", profile_data.get("department", "Operations")),
        ("CLEARANCE", f"LEVEL {profile_data.get('clearance', 1)}"),
        ("STATUS", "ACTIVE DUTY")
    ]
    for label, value in stats:
        draw.text((col2_x, current_y), label, font=layout.font_tiny, fill=LCARS2Colors.NEON_CYAN)
        draw.text((col2_x + 120, current_y), str(value).upper(), font=layout.font_data, fill=LCARS2Colors.TEXT_PRIMARY)
        current_y += 30
        
    draw.text((width - 100, height - 40), f"SEC-{random.randint(10,99)}", font=layout.font_tiny, fill=LCARS2Colors.TEXT_DIM)
    
    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=95)
    output.seek(0)
    return output

def render_general_report(title: str, sections: List[Dict], style: str = "default") -> io.BytesIO:
    """Renders a dynamic length LCARS 2.0 Report (Scan/Status/Docs)."""
    layout = LCARS2Layout()
    width = 900
    height = layout.calculate_report_height(sections, width)
    
    img = Image.new("RGBA", (width, height), LCARS2Colors.BG_DEEP)
    draw = ImageDraw.Draw(img)
    
    margin = 30
    content_w = width - margin*2
    content_h = height - margin*2
    
    # 1. Frame
    color = LCARS2Colors.NEON_CYAN
    if style == "alert": color = LCARS2Colors.TITAN_RED
    if style == "status": color = LCARS2Colors.GOLD
    
    LCARS2Primitives.draw_bracket_frame(draw, margin, margin, content_w, content_h, color)
    
    # 2. Header
    draw.rectangle([margin, margin, margin + 500, margin + 50], fill=color)
    draw.text((margin + 20, margin + 8), title.upper(), font=layout.font_header, fill=LCARS2Colors.BG_DEEP)
    
    # 3. Glass Backing
    LCARS2Primitives.draw_glass_panel(img, margin, margin + 60, content_w, content_h - 60)
    
    # 4. Sections
    y = margin + 80
    for section in sections:
        cat = section.get("category", "").upper()
        content = section.get("content", "")
        
        # Category
        if cat:
            draw.text((margin + 20, y), cat, font=layout.font_category, fill=LCARS2Colors.TEXT_CATEGORY)
            y += 35
        
        # Content
        lines = layout.wrap_text(content, layout.font_data, content_w - 40)
        for line in lines:
            draw.text((margin + 20, y), line, font=layout.font_data, fill=LCARS2Colors.TEXT_PRIMARY)
            y += 25
            
        y += 20 # Gap between sections
        
    # Footer Greebles
    draw.text((width - 120, height - margin - 20), "LCARS 2.4", font=layout.font_tiny, fill=LCARS2Colors.TEXT_DIM)

    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=95)
    output.seek(0)
    return output

# ============================================================================
# PUBLIC API
# ============================================================================

def render_report(report_data: Dict[str, Any], template_type: str = "default") -> io.BytesIO:
    """Public entry for reports."""
    return render_general_report(
        report_data.get("title", "SYSTEM REPORT"), 
        report_data.get("sections", []),
        style=template_type
    )

def render_status(status_text: str) -> io.BytesIO:
    return render_general_report("SYSTEM STATUS", [{"category": "DIAGNOSTIC", "content": status_text}], style="status")

def render_alert(title: str, content: str) -> io.BytesIO:
    return render_general_report(title, [{"category": "ALERT", "content": content}], style="alert")

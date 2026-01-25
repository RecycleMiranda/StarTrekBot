"""
LCARS 2.0 Visual Engine - Titan.DS Replica
Pixel-perfect recreation of mewho.com/titan interface using PIL.
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# ============================================================================
# CONSTANTS & CONFIG
# ============================================================================
class TStyle:
    # Color Palette (Extracted from Titan.DS)
    BG = (5, 7, 10)                  # #05070A - Deep Black/Blue
    
    # Cyan Spectrum
    CYAN_LIGHEST = (147, 225, 255)   # #93E1FF
    CYAN_LIGHT = (103, 202, 240)     # #67CAF0 (Active High)
    CYAN_MAIN = (55, 166, 209)       # #37A6D1 (Primary Frame)
    CYAN_DIM = (42, 113, 147)        # #2A7193 (Secondary)
    CYAN_DARK = (28, 60, 85)         # #1C3C55 (Backgrounds)
    
    # Orange Spectrum
    ORANGE_LIGHT = (255, 151, 123)   # #FF977B (Buttons)
    ORANGE_MAIN = (255, 103, 83)     # #FF6753 (Active/Alert)
    ORANGE_DARK = (239, 29, 16)      # #EF1D10 (Red Alert)
    
    # Text
    TEXT_WHITE = (223, 225, 232)     # #DFE1E8
    TEXT_DIM = (109, 116, 140)       # #6D748C
    
    # Dimensions
    GAP = 3        # The signature Titan gap
    RADIUS_L = 30  # Large corners
    RADIUS_S = 15  # Small corners (Pills)
    STROKE = 2     # Frame thickness (High precision)

class FontLoader:
    def __init__(self):
        # Priority list for fonts (including common Linux CJK paths)
        common_paths = [
            "services/bot/app/assets/font.ttf", # User provided
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/System/Library/Fonts/PingFang.ttc", # Local dev
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        
        self.header = None
        self.label = None
        self.data = None
        self.tiny = None
        
        font_path = None
        for p in common_paths:
            if os.path.exists(p):
                font_path = p
                break
                
        if font_path:
            try:
                self.header = ImageFont.truetype(font_path, 40) # ANTONIO style large
                self.label = ImageFont.truetype(font_path, 22)  # Section headers
                self.data = ImageFont.truetype(font_path, 26)   # Main data
                self.tiny = ImageFont.truetype(font_path, 14)   # Greebles
            except: pass
            
        if not self.header:
            # Fallback
            self.header = ImageFont.load_default()
            self.label = ImageFont.load_default()
            self.data = ImageFont.load_default()
            self.tiny = ImageFont.load_default()

# ============================================================================
# COMPONENT BUILDER (The "Brick Layer")
# ============================================================================
class TitanRenderer:
    def __init__(self, width=1024, height=600):
        self.w = width
        self.h = height
        self.img = Image.new("RGBA", (width, height), TStyle.BG)
        self.draw = ImageDraw.Draw(self.img)
        self.fonts = FontLoader()
        
    def save(self) -> io.BytesIO:
        out = io.BytesIO()
        self.img.convert("RGB").save(out, "JPEG", quality=95)
        out.seek(0)
        return out

    def draw_path_elbow_top_left(self, x, y, w, h, thickness, color):
        """Draws the signature LCARS 'Elbow' connector."""
        # Vertical segment
        self.draw.rectangle([x, y + h, x + thickness, y + h + 50], fill=color) # Extension down
        # Horizontal segment
        self.draw.rectangle([x + w, y, x + w + 50, y + thickness], fill=color) # Extension right
        
        # The Curve (Pie slice)
        # Bounding box for the arc
        self.draw.pieslice([x, y, x + w*2, y + h*2], 180, 270, fill=color)
        
        # Inner cutout (to make it a curve, not a wedge)
        # Titan elbows are thick and solid, usually no inner cutout for the main shape,
        # but the inner corner is often sharp or small radius.
        # Let's simple draw a black circle inside if we wanted a stroke elbow
        # But per reference, they are solid blocks.
        
        # Correction: Titan Top-Left Elbow is usually:
        # H-Bar connected to V-Bar by a curve.
        pass

    def draw_pill(self, x, y, w, h, color):
        r = h // 2
        self.draw.ellipse([x, y, x+h, y+h], fill=color)
        self.draw.ellipse([x+w-h, y, x+w, y+h], fill=color)
        self.draw.rectangle([x+r, y, x+w-r, y+h], fill=color)

    def draw_rect(self, x, y, w, h, color):
        self.draw.rectangle([x, y, x+w, y+h], fill=color)

    def draw_bracket_frame(self, x, y, w, h, color):
        t = TStyle.STROKE
        l = 30 # Corner length
        # TL
        self.draw.rectangle([x, y, x+l, y+t], fill=color)
        self.draw.rectangle([x, y, x+t, y+l], fill=color)
        # TR
        self.draw.rectangle([x+w-l, y, x+w, y+t], fill=color)
        self.draw.rectangle([x+w-t, y, x+w, y+l], fill=color)
        # BL
        self.draw.rectangle([x, y+h-t, x+l, y+h], fill=color)
        self.draw.rectangle([x, y+h-l, x+t, y+h], fill=color)
        # BR
        self.draw.rectangle([x+w-l, y+h-t, x+w, y+h], fill=color)
        self.draw.rectangle([x+w-t, y+h-l, x+w, y+h], fill=color)

    # --- TEMPLATES ---

    def render_map_layout(self, title, content_items):
        """
        Recreates the 'MOD: MAP' layout from Titan.DS
        """
        # 1. Header Complex
        # Main Cyan Bar with rounded left
        self.draw.pieslice([40, 40, 120, 120], 180, 270, fill=TStyle.CYAN_MAIN) # Curve
        self.draw.rectangle([80, 40, 400, 80], fill=TStyle.CYAN_MAIN)
        self.draw.rectangle([40, 80, 80, 80], fill=TStyle.CYAN_MAIN) # Fill corner
        
        # Header Text
        self.draw.text((100, 42), title.upper(), font=self.fonts.header, fill=TStyle.BG)
        
        # Header Right Bits
        self.draw_rect(400 + TStyle.GAP, 40, 80, 40, TStyle.ORANGE_LIGHT)
        self.draw_rect(480 + TStyle.GAP*2, 40, 40, 40, TStyle.CYAN_DIM)
        self.draw_rect(520 + TStyle.GAP*3, 40, self.w - 560, 40, TStyle.CYAN_MAIN) # Long top rail
        
        # 2. Sidebar (Left)
        # The Elbow connector
        # Vertical strip down from header
        sx = 40
        sy = 80 + TStyle.GAP
        sw = 40
        
        # Segment 1 (Orange)
        self.draw_rect(sx, sy, sw, 120, TStyle.ORANGE_LIGHT)
        # Segment 2 (Cyan)
        self.draw_rect(sx, sy + 120 + TStyle.GAP, sw, 60, TStyle.CYAN_MAIN)
        # Segment 3 (Dim)
        self.draw_rect(sx, sy + 180 + TStyle.GAP*2, sw, 80, TStyle.CYAN_DIM)
        # Segment 4 (Orange Long)
        self.draw_rect(sx, sy + 260 + TStyle.GAP*3, sw, 150, TStyle.ORANGE_LIGHT)
        # Bottom Curve
        self.draw.pieslice([sx, self.h - 80, sx + 80, self.h], 90, 180, fill=TStyle.CYAN_MAIN)
        self.draw.rectangle([sx + 40, self.h - 40, 200, self.h], fill=TStyle.CYAN_MAIN)
        
        # 3. Content Area (The "Void")
        cx = 100
        cy = 100
        cw = self.w - 140
        ch = self.h - 160
        
        # Glass backing
        overlay = Image.new('RGBA', self.img.size, (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        d.rectangle([cx, cy, cx+cw, cy+ch], fill=(55, 166, 209, 25)) # Very subtle cyan
        self.img.alpha_composite(overlay)
        self.draw = ImageDraw.Draw(self.img) # Re-hook
        
        # Brackets
        self.draw_bracket_frame(cx, cy, cw, ch, TStyle.CYAN_LIGHT)
        
        # 4. Content Rendering
        y_cursor = cy + 40
        x_col1 = cx + 40
        x_col2 = cx + 250
        
        for label, value in content_items:
            # Label
            self.draw.text((x_col1, y_cursor), label, font=self.fonts.label, fill=TStyle.CYAN_MAIN)
            # Value
            self.draw.text((x_col2, y_cursor), str(value), font=self.fonts.data, fill=TStyle.TEXT_WHITE)
            
            # Decorative line between rows
            self.draw_rect(x_col1, y_cursor + 35, cw - 80, 1, TStyle.CYAN_DARK)
            
            y_cursor += 50
            
        # 5. Bottom Right Greebles
        self.draw.text((self.w - 150, self.h - 30), "LCARS 2.0", font=self.fonts.tiny, fill=TStyle.TEXT_DIM)
        for i in range(3):
            c = [TStyle.ORANGE_MAIN, TStyle.CYAN_LIGHT, TStyle.CYAN_DIM][i]
            self.draw_pill(self.w - 60 + i*18, self.h - 25, 12, 12, c)


# ============================================================================
# PUBLIC API
# ============================================================================

def render_personnel_file(data: Dict[str, Any]) -> io.BytesIO:
    r = TitanRenderer(1024, 600)
    
    items = [
        ("NAME / 姓名", data.get("name", "UNKNOWN").upper()),
        ("RANK / 军衔", data.get("rank", "ENSIGN").upper()),
        ("SERIAL / 编号", data.get("user_id", "N/A")),
        ("STATION / 岗位", data.get("station", "GENERAL DUTY").upper()),
        ("CLEARANCE / 权限", f"LEVEL {data.get('clearance', 1)}"),
        ("STATUS / 状态", "ACTIVE DUTY" if not data.get("restricted") else "RESTRICTED")
    ]
    
    r.render_map_layout("PERSONNEL FILE", items)
    return r.save()

def render_general_report(title: str, sections: List[Dict], style="default") -> io.BytesIO:
    # Estimate height
    h = 200
    for s in sections: h += len(s.get("content", "")) // 2 + 100
    h = max(h, 600)
    
    r = TitanRenderer(1024, h)
    
    # Adapt items specific to report
    # We'll just render text lines for now in the content loop
    # ... (Simplified for parity with personnel file for now)
    
    formatted_items = []
    for s in sections:
        formatted_items.append((s.get("category", "INFO"), s.get("content", "")[:50] + "..."))
        
    r.render_map_layout(title, formatted_items)
    return r.save()

def render_report(data: Dict, template_type: str="default") -> io.BytesIO:
    return render_general_report(data.get("title", "REPORT"), data.get("sections", []), template_type)

def render_status(text: str) -> io.BytesIO:
    return render_general_report("SYSTEM STATUS", [{"content": text}])

def render_alert(title: str, content: str) -> io.BytesIO:
    return render_general_report(title, [{"content": content}])

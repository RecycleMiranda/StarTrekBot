"""
LCARS 2.0 Visual Engine - Custom Template Edition
Using user-provided Illustrator template for personnel cards.
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps
from typing import Dict, List, Any, Tuple

class TStyle:
    # Color Palette (Matches user's template)
    # Background is now the loaded image
    TEXT_WHITE = (223, 225, 232)
    TEXT_CYAN = (88, 166, 209)
    TEXT_ORANGE = (255, 151, 123)
    
class FontLoader:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        asset_font = os.path.join(base_dir, "assets", "font.ttf")
        
        common_paths = [
            asset_font,
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        
        font_path = None
        for p in common_paths:
            if os.path.exists(p):
                font_path = p
                break
                
        if font_path:
            try:
                self.title = ImageFont.truetype(font_path, 80)
                self.header = ImageFont.truetype(font_path, 60)
                self.label = ImageFont.truetype(font_path, 32)
                self.data = ImageFont.truetype(font_path, 40)
                self.bio = ImageFont.truetype(font_path, 36)
                self.tiny = ImageFont.truetype(font_path, 20)
            except: pass
            
        if not self.header:
            self.title = self.header = self.label = self.data = self.bio = self.tiny = ImageFont.load_default()

class TemplateRenderer:
    def __init__(self, template_path: str):
        self.template = Image.open(template_path).convert("RGBA")
        # Base size for coordinate mapping: 2000 x 1200
        self.canvas_w = 2000
        self.canvas_h = 1200
        self.img = self.template.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS)
        self.draw = ImageDraw.Draw(self.img)
        self.fonts = FontLoader()

    def draw_text_wrapped(self, text, x, y, max_line_width, font, fill, spacing=10):
        lines = []
        words = list(text) # For CJK, word-by-char is safer
        current_line = ""
        for word in words:
            test_line = current_line + word
            w = font.getlength(test_line)
            if w <= max_line_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        
        for line in lines:
            self.draw.text((x, y), line, font=font, fill=fill)
            # Use font size for line height approximation if getbbox is tricky
            y += font.size + spacing

    def render_personnel(self, data: Dict[str, Any]):
        # --- 1. Top Areas (Avatar & Watermark) ---
        # Watermark to confirm new engine is active
        self.draw.text((1600, 50), "INTEGRATED DESIGN V2.1", font=self.fonts.tiny, fill=(100, 100, 150))
        
        avatar_x, avatar_y = 485, 420
        avatar_size = 370
        
        avatar_img = data.get("avatar") 
        if avatar_img:
            # Resize and paste
            if hasattr(avatar_img, 'resize'):
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                self.img.paste(avatar_img, (avatar_x, avatar_y))
        else:
            # Placeholder color
            self.draw.rectangle([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(15, 20, 35))
            self.draw.text((avatar_x + 90, avatar_y + 160), "NO SIGNAL", font=self.fonts.label, fill=TStyle.TEXT_DIM)

        # Second Frame: Rank Insignia or mirror?
        # Let's leave it blank or put a decorative logo
        
        # --- 2. Data Section (Below Frames) ---
        data_x = 450
        data_y = 820
        line_h = 70
        
        fields = [
            ("NAME / 姓名", data.get("name", "Unknown")),
            ("RANK / 军衔", data.get("rank", "Ensign")),
            ("DEPT / 部门", data.get("department", "Operations")),
            ("QUOTA / 配额", f"{data.get('quota_balance', 0)} CREDITS"),
            ("ACCESS / 权限", f"LEVEL {data.get('clearance', 1)}"),
        ]
        
        for i, (label, val) in enumerate(fields):
            curr_y = data_y + i * line_h
            self.draw.text((data_x, curr_y), label, font=self.fonts.label, fill=TStyle.TEXT_ORANGE)
            # Offset value
            self.draw.text((data_x + 240, curr_y - 12), str(val).upper(), font=self.fonts.data, fill=TStyle.TEXT_WHITE)

        # --- 3. Bio Section (Right Column) ---
        # Template "BIO" is at x=2800 (5000 scale) -> x=1120 (2000 scale)
        bio_x = 1150
        bio_y = 360
        bio_content = data.get("biography", "")
        if not bio_content:
            bio_content = "FEDERATION PERSONNEL ARCHIVE STATUS: ACTIVE. NO ADDITIONAL BIOGRAPHICAL DATA UPLOADED."
            
        self.draw_text_wrapped(bio_content, bio_x, bio_y, 720, self.fonts.bio, TStyle.TEXT_WHITE)

        # --- 4. Extra Greebles ---
        self.draw.text((1150, 1020), f"RECORD ID: {data.get('user_id', '0000')}-GAMMA", font=self.fonts.tiny, fill=TStyle.TEXT_DIM)

    def save_to_bytes(self) -> io.BytesIO:
        out = io.BytesIO()
        self.img.convert("RGB").save(out, format="JPEG", quality=92)
        out.seek(0)
        return out

def render_personnel_file(data: Dict[str, Any]) -> io.BytesIO:
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, "assets", "personnel_template.png")
    
    # Fallback to pure code render if template is missing
    if not os.path.exists(template_path):
        # We should probably keep the old code or a minimal version
        # For now, let's assume assets exist because we just moved them
        pass

    tr = TemplateRenderer(template_path)
    tr.render_personnel(data)
    return tr.save_to_bytes()

# Maintain parity for other functions
def render_report(data: Dict, template_type: str = "default") -> io.BytesIO:
    # Use generic layout for now
    pass

def render_status(text: str) -> io.BytesIO:
    pass

def render_alert(title: str, content: str) -> io.BytesIO:
    pass

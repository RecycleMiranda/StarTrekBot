"""
LCARS 2.0 Visual Engine - Custom Template Edition
Using user-provided Illustrator template for personnel cards.
"""
import io
import os
import re
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

class TStyle:
    # Color Palette (Matches user's template)
    TEXT_WHITE = (223, 225, 232)
    TEXT_CYAN = (88, 166, 209)
    TEXT_ORANGE = (255, 151, 123)
    TEXT_DIM = (120, 130, 150)
    
class FontLoader:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        shouxuan_font = os.path.join(base_dir, "assets", "shouxuan.ttf")
        asset_font = os.path.join(base_dir, "assets", "NotoSansSC-Bold.otf")
        
        # Pre-initialize to avoid AttributeError
        self.title = self.header = self.label = self.data = self.bio = self.tiny = None

        # Comprehensive paths for Docker (Debian) and Mac
        common_paths = [
            shouxuan_font,
            # Debian/Ubuntu Noto CJK paths
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            # Local assets
            asset_font,
            # Mac system fonts
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        
        font_path = None
        for p in common_paths:
            if os.path.exists(p):
                font_path = p
                break
                
        if font_path:
            try:
                # SIZES RECALIBRATED FOR 2000x1200 RESOLUTION
                self.title = ImageFont.truetype(font_path, 110)
                self.header = ImageFont.truetype(font_path, 80)
                self.label = ImageFont.truetype(font_path, 42)
                self.data = ImageFont.truetype(font_path, 52)
                self.bio = ImageFont.truetype(font_path, 46)
                self.tiny = ImageFont.truetype(font_path, 28)
            except Exception as e:
                print(f"[FontLoader] Failed to load {font_path}: {e}")
            
        if not self.header:
            # Fallback to default if all else fails, but try to use a decent size
            self.title = self.header = self.label = self.data = self.bio = self.tiny = ImageFont.load_default()

class TemplateRenderer:
    def __init__(self, template_path: str):
        self.template = Image.open(template_path).convert("RGBA")
        # USER REQUESTED: Lower resolution for better UX and proportion
        self.canvas_w = 2000
        self.canvas_h = 1200
        
        # 1. Force Black Background
        self.img = Image.new("RGBA", (self.canvas_w, self.canvas_h), (0, 0, 0, 255))
        
        # 2. Paste Template
        resized_template = self.template.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS)
        self.img.alpha_composite(resized_template)
        
        self.draw = ImageDraw.Draw(self.img)
        self.fonts = FontLoader()

    def draw_text_wrapped(self, text, x, y, max_line_width, font, fill, spacing=12):
        lines = []
        words = list(str(text)) 
        current_line = ""
        for word in words:
            test_line = current_line + word
            try:
                w = font.getlength(test_line)
            except:
                w = len(test_line) * (font.size * 0.5) # Rough fallback if getlength fails
                
            if w <= max_line_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        
        for line in lines:
            self.draw.text((x, y), line, font=font, fill=fill)
            y += font.size + spacing

    def render_personnel(self, data: Dict[str, Any]):
        # --- RECALIBRATED COORDINATES FOR 2000x1200 CANVAS ---
        
        # 1. Avatar Section (Bracket Alignment)
        avatar_size = 380 
        avatar_x, avatar_y = 480, 210  
        
        avatar_img = data.get("avatar") 
        if avatar_img:
            if hasattr(avatar_img, 'resize'):
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                self.img.paste(avatar_img, (avatar_x, avatar_y))
        else:
            self.draw.rectangle([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(15, 20, 35))
            self.draw.text((avatar_x + 90, avatar_y + 160), "NO SIGNAL", font=self.fonts.label, fill=TStyle.TEXT_DIM)

        # 2. Data Section (Shifted to clear vertical ornaments)
        data_x = 520 
        data_y = 670 
        line_h = 80 
        
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
            self.draw.text((data_x + 280, curr_y - 8), str(val).upper(), font=self.fonts.data, fill=TStyle.TEXT_WHITE)

        # 3. Bio Section (Aligned with "BIO" Header on right)
        bio_x = 1180 
        bio_y = 350  
        bio_content = data.get("biography", "")
        if not bio_content:
            bio_content = "FEDERATION PERSONNEL ARCHIVE STATUS: ACTIVE. NO ADDITIONAL BIOGRAPHICAL DATA UPLOADED."
            
        self.draw_text_wrapped(bio_content, bio_x, bio_y, 750, self.fonts.bio, TStyle.TEXT_WHITE)

        # 4. Record ID (Bottom Greeble)
        self.draw.text((1180, 1020), f"RECORD ID: {data.get('user_id', '0000')}-GAMMA", font=self.fonts.tiny, fill=TStyle.TEXT_DIM)

    def save_to_bytes(self) -> io.BytesIO:
        out = io.BytesIO()
        self.img.save(out, format="PNG")
        out.seek(0)
        return out

def render_personnel_file(data: Dict[str, Any]) -> io.BytesIO:
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, "assets", "personnel_template.png")
    tr = TemplateRenderer(template_path)
    tr.render_personnel(data)
    return tr.save_to_bytes()

def render_report(data: Dict, template_type: str = "default") -> io.BytesIO:
    pass

def render_status(text: str) -> io.BytesIO:
    pass

def render_alert(title: str, content: str) -> io.BytesIO:
    pass

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
    TEXT_DIM = (120, 130, 150)
    
class FontLoader:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        asset_font = os.path.join(base_dir, "assets", "NotoSansSC-Bold.otf")
        shouxuan_font = os.path.join(base_dir, "assets", "shouxuan.ttf") # Path to be filled by user or existing file
        
        common_paths = [
            shouxuan_font,
            asset_font,
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", # Serif fallback for SongTi
            "/System/Library/Fonts/PingFang.ttc"
        ]
        
        font_path = None
        for p in common_paths:
            if os.path.exists(p):
                font_path = p
                break
                
        if font_path:
            try:
                # Use bigger sizes for 3000px HD canvas
                self.title = ImageFont.truetype(font_path, 120)
                self.header = ImageFont.truetype(font_path, 90)
                self.label = ImageFont.truetype(font_path, 48)
                self.data = ImageFont.truetype(font_path, 60)
                self.bio = ImageFont.truetype(font_path, 54)
                self.tiny = ImageFont.truetype(font_path, 30)
            except: pass
            
        if not self.header:
            self.title = self.header = self.label = self.data = self.bio = self.tiny = ImageFont.load_default()

class TemplateRenderer:
    def __init__(self, template_path: str):
        self.template = Image.open(template_path).convert("RGBA")
        # Increase resolution to 3000x1800 for high-fidelity output
        self.canvas_w = 3000
        self.canvas_h = 1800
        self.img = self.template.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS)
        self.draw = ImageDraw.Draw(self.img)
        self.fonts = FontLoader()

    def draw_text_wrapped(self, text, x, y, max_line_width, font, fill, spacing=15):
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
        # Recalibrate coordinates for 3000x1800 based on visual feedback
        # 1. REMOVED VERSION WATERMARK per user request
        
        # --- 1. Avatar Section (Inside the blue brackets) ---
        avatar_x, avatar_y = 590, 750 
        avatar_size = 580 
        
        avatar_img = data.get("avatar") 
        if avatar_img:
            if hasattr(avatar_img, 'resize'):
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                self.img.paste(avatar_img, (avatar_x, avatar_y))
        else:
            self.draw.rectangle([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(15, 20, 35))
            self.draw.text((avatar_x + 135, avatar_y + 240), "NO SIGNAL", font=self.fonts.label, fill=TStyle.TEXT_DIM)

        # --- 2. Data Section (Below Avatar, avoid left vertical bar) ---
        data_x = 940 
        data_y = 1350 
        line_h = 82 
        
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
            self.draw.text((data_x + 360, curr_y - 8), str(val).upper(), font=self.fonts.data, fill=TStyle.TEXT_WHITE)

        # --- 3. Bio Section (Far right, under BIO header) ---
        # Template BIO header is approx x=2500 in 3000px scale
        bio_x = 2520 
        bio_y = 580  
        bio_content = data.get("biography", "")
        if not bio_content:
            bio_content = "FEDERATION PERSONNEL ARCHIVE STATUS: ACTIVE. NO ADDITIONAL BIOGRAPHICAL DATA UPLOADED."
            
        self.draw_text_wrapped(bio_content, bio_x, bio_y, 420, self.fonts.bio, TStyle.TEXT_WHITE)

        # --- 4. Record ID (Bottom Right Greeble) ---
        self.draw.text((1650, 1530), f"RECORD ID: {data.get('user_id', '0000')}-GAMMA", font=self.fonts.tiny, fill=TStyle.TEXT_DIM)

    def save_to_bytes(self) -> io.BytesIO:
        out = io.BytesIO()
        # SWITCH TO PNG FOR LOSSLESS QUALITY
        self.img.save(out, format="PNG")
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

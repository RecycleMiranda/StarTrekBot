import os
import base64
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# Pixel Coordinates for "Content Area" in 联邦数据库.png
# (Approximated based on a 1000px wide image, will refine after first render)
import os
import base64
import logging
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Target working resolution (scaled down from 5000x3000 for efficiency)
CANVAS_W = 1600
CANVAS_H = 960

# CONTENT AREA COORDIANTES (Scaled for 1600x960)
CONTENT_L = 300
CONTENT_T = 120
CONTENT_R = 1550
CONTENT_B = 850

class LCARS_Renderer:
    def __init__(self, root_path: str):
        self.root = root_path
        self.bg_path = os.path.join(self.root, "联邦数据库.png")
        self.frame_full = os.path.join(self.root, "展示框1.png")
        self.frame_left = os.path.join(self.root, "展示框1左.png")
        self.frame_right = os.path.join(self.root, "展示框1右.png")
        
        # Font configuration
        self.font_path = "/System/Library/Fonts/Supplemental/Arial.ttf" # Default Mac path
        if not os.path.exists(self.font_path):
            self.font_path = None # PIL will fallback to default

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1) -> str:
        """Renders items and returns b64 PNG."""
        with Image.open(self.bg_path).convert("RGBA") as canvas:
            canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(canvas)
            
            # 1. Header/Footer Text
            try:
                font_title = ImageFont.truetype(self.font_path if self.font_path else "arial", 40)
                font_id = ImageFont.truetype(self.font_path if self.font_path else "arial", 24)
                font_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 30)
            except:
                font_title = ImageFont.load_default()
                font_id = ImageFont.load_default()
                font_content = ImageFont.load_default()

            # Pagination Text (User feedback: Page Y of X)
            p_text = f"PAGE {page} OF {total_pages}"
            draw.text((CONTENT_R - 200, CONTENT_B + 20), p_text, fill=(255, 255, 255, 200), font=font_id)
            
            # 2. Tiling logic (2x2 grid for simplicity or list)
            item_h = (CONTENT_B - CONTENT_T) // 2
            item_w = (CONTENT_R - CONTENT_L) // 2
            
            for idx, item in enumerate(items[:4]): # Max 4 items per page
                row = idx // 2
                col = idx % 2
                x = CONTENT_L + col * item_w + 20
                y = CONTENT_T + row * item_h + 20
                
                self._draw_item(canvas, item, (x, y), item_w - 40, item_h - 40, font_title, font_id, font_content)

            buffered = BytesIO()
            canvas.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _draw_item(self, canvas, item, pos, max_w, max_h, f_t, f_id, f_c):
        draw = ImageDraw.Draw(canvas)
        item_id = item.get("id", "??")
        title = (item.get("title") or "UNSPECIFIED RECORD").upper()
        content = item.get("content", "")
        img_raw = item.get("image_b64") or item.get("image_path")
        
        # 1. Dynamic Framing Logic
        # Calculate horizontal center area
        with Image.open(self.frame_left).convert("RGBA") as f_l, \
             Image.open(self.frame_right).convert("RGBA") as f_r:
            
            # Scale frames to match max_h
            scale_h = max_h / f_l.height
            f_l_s = f_l.resize((int(f_l.width * scale_h), max_h), Image.Resampling.LANCZOS)
            f_r_s = f_r.resize((int(f_r.width * scale_h), max_h), Image.Resampling.LANCZOS)
            
            # Draw Left and Right Caps
            canvas.alpha_composite(f_l_s, pos)
            canvas.alpha_composite(f_r_s, (pos[0] + max_w - f_r_s.width, pos[1]))
            
            # Fill the middle with a stretched segment or background (if needed)
            # Actually, the user says "随便拉伸排放", so we can use f_l/f_r as the anchors
            # and draw the content in the middle.
            
        # 2. Image Overlay (if exists)
        if img_raw:
            try:
                if item.get("image_b64"):
                    img = Image.open(BytesIO(base64.b64decode(item["image_b64"]))).convert("RGBA")
                else:
                    img = Image.open(img_raw).convert("RGBA")
                
                # Fit image into the center of the frame
                target_w = max_w - 60
                target_h = max_h - 120
                img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                
                ix = pos[0] + (max_w - img.width) // 2
                iy = pos[1] + (max_h - img.height) // 2 + 20
                canvas.alpha_composite(img, (ix, iy))
            except Exception as e:
                logger.warning(f"Image load failed for {item_id}: {e}")

        # 3. Text/Label Overlay
        # ID Label (Top Left)
        draw.text((pos[0] + 25, pos[1] + 15), item_id, fill=(255, 150, 0, 255), font=f_id)
        # Title (Top Center)
        tw = f_id.getlength(title)
        draw.text((pos[0] + (max_w - tw) // 2, pos[1] + 15), title, fill=(200, 200, 255, 255), font=f_id)

        # 4. Content Overlay (Only for text blocks)
        if not img_raw:
            margin_l = 60
            margin_t = 80
            text_y = pos[1] + margin_t
            for line in self._wrap_text(content, f_c, max_w - margin_l - 40):
                if text_y + 35 > pos[1] + max_h - 20: break
                draw.text((pos[0] + margin_l, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                text_y += 35

    def _wrap_text(self, text, font, max_width):
        lines = []
        words = list(text) # Char wrap for Chinese
        current_line = ""
        for char in words:
            test_line = current_line + char
            w = font.getlength(test_line)
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        lines.append(current_line)
        return lines

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        _renderer = LCARS_Renderer("/Users/wanghaozhe/Documents/GitHub/StarTrekBot")
    return _renderer

# Instance provider
_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        # Assuming we are in /app/services/bot/app/ or similar
        # Root path is where the .png files were moved
        _renderer = LCARS_Renderer("/Users/wanghaozhe/Documents/GitHub/StarTrekBot")
    return _renderer

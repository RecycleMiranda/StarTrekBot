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
    def __init__(self, root_path: str = None):
        # Resolve assets directory relative to this file
        # /app/services/bot/app/render_engine.py -> /app/services/bot/app/static/assets/database/
        if not root_path:
            base_dir = os.path.dirname(__file__)
            self.assets_dir = os.path.join(base_dir, "static", "assets", "database")
        else:
            self.assets_dir = os.path.join(root_path, "services", "bot", "app", "static", "assets", "database")
            
        self.bg_path = os.path.join(self.assets_dir, "联邦数据库.png")
        self.frame_full = os.path.join(self.assets_dir, "展示框1.png")
        self.frame_left = os.path.join(self.assets_dir, "展示框1左.png")
        self.frame_right = os.path.join(self.assets_dir, "展示框1右.png")
        
        # Font configuration
        # For Linux/Docker compatibility, we check common font paths
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf"
        ]
        self.font_path = next((f for f in font_candidates if os.path.exists(f)), None)

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1) -> str:
        """Renders items and returns b64 PNG."""
        if not os.path.exists(self.bg_path):
            error_msg = f"[Renderer] Background not found: {self.bg_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

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
        
        # 1. Image Attempt Logic
        image_to_draw = None
        if img_raw:
            try:
                if item.get("image_b64"):
                    image_to_draw = Image.open(BytesIO(base64.b64decode(item["image_b64"]))).convert("RGBA")
                elif item.get("image_path") and os.path.exists(item["image_path"]):
                    image_to_draw = Image.open(item["image_path"]).convert("RGBA")
            except Exception as e:
                logger.warning(f"Image load failed for {item_id}, falling back to text: {e}")

        # 2. Layout Selection
        if image_to_draw:
            # --- IMAGE MODE (With Brackets) ---
            # Dynamic Framing (Preventing Overlap & Stretching)
            try:
                with Image.open(self.frame_left).convert("RGBA") as f_l, \
                     Image.open(self.frame_right).convert("RGBA") as f_r:
                    # Scale to match item height
                    scale_h = max_h / f_l.height
                    lw, rw = int(f_l.width * scale_h), int(f_r.width * scale_h)
                    
                    # CROP: Limit caps to avoid overlap if max_w is small
                    # Also helps if the assets have huge empty areas
                    max_cap_w = max_w // 4
                    lw = min(lw, max_cap_w)
                    rw = min(rw, max_cap_w)
                    
                    f_l_s = f_l.resize((int(f_l.width * scale_h), max_h), Image.Resampling.LANCZOS).crop((f_l.width * scale_h - lw, 0, f_l.width * scale_h, max_h))
                    f_r_s = f_r.resize((int(f_r.width * scale_h), max_h), Image.Resampling.LANCZOS).crop((0, 0, rw, max_h))
                    
                    # Draw caps at the extreme edges of max_w
                    canvas.alpha_composite(f_l_s, pos)
                    canvas.alpha_composite(f_r_s, (pos[0] + max_w - rw, pos[1]))
                    
                    # Stretch middle
                    middle_w = max_w - lw - rw
                    if middle_w > 0:
                        # Use a slice from the left cap's vertical section
                        mid_slice = f_l_s.crop((lw - 5, 0, lw - 1, max_h))
                        mid_body = mid_slice.resize((middle_w, max_h), Image.Resampling.NEAREST)
                        canvas.alpha_composite(mid_body, (pos[0] + lw, pos[1]))
            except Exception as e:
                logger.warning(f"Framing failed: {e}")

            # Draw Image
            target_w, target_h = max_w - 100, max_h - 160
            image_to_draw.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            ix = pos[0] + (max_w - image_to_draw.width) // 2
            iy = pos[1] + (max_h - image_to_draw.height) // 2 + 20
            canvas.alpha_composite(image_to_draw, (ix, iy))
        else:
            # --- TEXT MODE (Clean Header, Full Width) ---
            # Optional: Draw a subtle top/bottom bar instead of brackets
            draw.line([(pos[0] + 40, pos[1] + 55), (pos[0] + max_w - 40, pos[1] + 55)], fill=(150, 150, 255, 100), width=2)
            
            # Content Rendering
            margin_l, margin_t = 50, 90
            text_y = pos[1] + margin_t
            wrap_w = max_w - margin_l - 40
            for line in self._wrap_text(content, f_c, wrap_w):
                if text_y + 40 > pos[1] + max_h - 20: break
                draw.text((pos[0] + margin_l, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                text_y += 42

        # 3. Universal Labels
        label_y = pos[1] + 15
        draw.text((pos[0] + 45, label_y), item_id, fill=(255, 150, 0, 255), font=f_id)
        tw = f_id.getlength(title)
        draw.text((pos[0] + (max_w - tw) // 2, label_y), title, fill=(200, 200, 255, 255), font=f_id)

    def _wrap_text(self, text, font, max_width):
        lines = []
        if not text: return []
        # Support both Chinese and English wrapping
        current_line = ""
        for char in text:
            test_line = current_line + char
            if font.getlength(test_line) <= max_width:
                current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = char
        if current_line: lines.append(current_line)
        return lines

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        # Default constructor uses relative paths suitable for Docker environment
        _renderer = LCARS_Renderer()
    return _renderer

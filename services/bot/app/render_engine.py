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
        """Renders items using a strict 2x2 absolute grid."""
        if not os.path.exists(self.bg_path):
            logger.error(f"[Renderer] Background not found: {self.bg_path}")
            raise FileNotFoundError(f"Background not found: {self.bg_path}")

        with Image.open(self.bg_path).convert("RGBA") as canvas:
            canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(canvas)
            
            # --- 1. Font Hardware Initialization ---
            try:
                f_title = ImageFont.truetype(self.font_path if self.font_path else "arial", 36)
                f_id = ImageFont.truetype(self.font_path if self.font_path else "arial", 22)
                f_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 28)
            except:
                f_title = f_id = f_content = ImageFont.load_default()

            # Pagination (Bottom Right)
            p_text = f"PAGE {page} OF {total_pages}"
            draw.text((CANVAS_W - 250, CANVAS_H - 80), p_text, fill=(255, 255, 255, 180), font=f_id)
            
            # --- 2. Absolute 2x2 Grid Definition ---
            # Slots: [ (x, y, w, h) ]
            grid = [
                (320, 130, 600, 360), # 1A (Top Left)
                (940, 130, 600, 360), # 1B (Top Right)
                (320, 510, 600, 360), # 2A (Bottom Left)
                (940, 510, 600, 360)  # 2B (Bottom Right)
            ]
            
            labels = ["1A", "1B", "2A", "2B"]
            
            for idx, item in enumerate(items[:4]):
                x, y, w, h = grid[idx]
                item_copy = item.copy()
                item_copy["id"] = labels[idx] # Force ID for grid alignment
                self._draw_item_overhaul(canvas, item_copy, (x, y), w, h, f_title, f_id, f_content)

            buffered = BytesIO()
            canvas.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _draw_item_overhaul(self, canvas, item, pos, max_w, max_h, f_t, f_id, f_c):
        """Absolute item renderer with distinct Image/Text modes."""
        draw = ImageDraw.Draw(canvas)
        item_id = item.get("id", "??")
        title = (item.get("title") or "TECHNICAL RECORD").upper()
        content = item.get("content", "").strip()
        img_raw = item.get("image_b64") or item.get("image_path")
        
        # --- 1. Payload Analysis ---
        image_to_draw = None
        if img_raw:
            try:
                if item.get("image_b64"):
                    image_to_draw = Image.open(BytesIO(base64.b64decode(item["image_b64"]))).convert("RGBA")
                elif os.path.exists(str(img_raw)):
                    image_to_draw = Image.open(img_raw).convert("RGBA")
            except Exception as e:
                logger.warning(f"[Renderer] Image load failed for {item_id}: {e}")

        # --- 2. Layout Branching ---
        if image_to_draw:
            # --- IMAGE MODE (Stretched Brackets) ---
            try:
                with Image.open(self.frame_left).convert("RGBA") as f_l, \
                     Image.open(self.frame_right).convert("RGBA") as f_r:
                    # Height adjustment
                    scale_h = max_h / f_l.height
                    lw, rw = int(f_l.width * scale_h), int(f_r.width * scale_h)
                    f_l_s = f_l.resize((lw, max_h), Image.Resampling.LANCZOS)
                    f_r_s = f_r.resize((rw, max_h), Image.Resampling.LANCZOS)
                    
                    # Fill Middle (Body Stretch)
                    mid_w = max_w - lw - rw
                    if mid_w > 0:
                        mid_slice = f_l_s.crop((lw-4, 0, lw-1, max_h))
                        mid_body = mid_slice.resize((mid_w, max_h), Image.Resampling.NEAREST)
                        canvas.alpha_composite(mid_body, (pos[0] + lw, pos[1]))
                    
                    # Draw Caps
                    canvas.alpha_composite(f_l_s, pos)
                    canvas.alpha_composite(f_r_s, (pos[0] + max_w - rw, pos[1]))
            except: pass

            # Thumbnail fitting
            tw, th = max_w - 90, max_h - 140
            image_to_draw.thumbnail((tw, th), Image.Resampling.LANCZOS)
            ix = pos[0] + (max_w - image_to_draw.width) // 2
            iy = pos[1] + (max_h - image_to_draw.height) // 2 + 20
            canvas.alpha_composite(image_to_draw, (ix, iy))
        else:
            # --- TEXT MODE (Direct Briefing Style) ---
            # Visual separator line
            line_y = pos[1] + 55
            draw.line([(pos[0] + 30, line_y), (pos[0] + max_w - 30, line_y)], fill=(150, 150, 255, 80), width=2)
            
            # Text body rendering
            wrap_w = max_w - 60
            lines = self._wrap_text(content, f_c, wrap_w)
            text_y = pos[1] + 85
            for line in lines:
                if text_y + 35 > pos[1] + max_h - 10: break
                draw.text((pos[0] + 30, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                text_y += 38

        # --- 3. Header Overlay (Universal) ---
        header_y = pos[1] + 15
        # ID Tag
        draw.text((pos[0] + 35, header_y), item_id, fill=(255, 170, 0, 255), font=f_id)
        # Title
        title_w = f_id.getlength(title)
        draw.text((pos[0] + (max_w - title_w) // 2, header_y), title, fill=(200, 200, 255, 255), font=f_id)

    def _wrap_text(self, text, font, max_width):
        if not text: return []
        lines = []
        curr = ""
        for char in text:
            test = curr + char
            if font.getlength(test) <= max_width:
                curr = test
            else:
                if curr: lines.append(curr)
                curr = char
        if curr: lines.append(curr)
        return lines

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        # Default constructor uses relative paths suitable for Docker environment
        _renderer = LCARS_Renderer()
    return _renderer

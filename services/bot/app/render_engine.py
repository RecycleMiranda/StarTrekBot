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

# FINAL COORDINATE DEFINITIONS
CONTENT_L = 520  # Safe zone to clear all sidebar assets
CONTENT_T = 160
CONTENT_W = 1040 # Full breadth of the right-side database area
CONTENT_B = 860
CONTENT_H_TOTAL = CONTENT_B - CONTENT_T

class LCARS_Renderer:
    def __init__(self, root_path: str = None):
        if not root_path:
            base_dir = os.path.dirname(__file__)
            self.assets_dir = os.path.join(base_dir, "static", "assets", "database")
        else:
            self.assets_dir = os.path.join(root_path, "services", "bot", "app", "static", "assets", "database")
            
        self.bg_path = os.path.join(self.assets_dir, "联邦数据库.png")
        self.frame_left = os.path.join(self.assets_dir, "展示框1左.png")
        self.frame_right = os.path.join(self.assets_dir, "展示框1右.png")
        
        # Robust Font Discovery (Mac/Linux/Universal)
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "arial.ttf"
        ]
        self.font_path = next((f for f in font_candidates if os.path.exists(f)), None)

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1) -> str:
        """Renders items using a Dynamic Vertical List to maximize UI space."""
        if not os.path.exists(self.bg_path):
            logger.error(f"[Renderer] Background not found: {self.bg_path}")
            raise FileNotFoundError(f"Background not found: {self.bg_path}")

        try:
            with Image.open(self.bg_path).convert("RGBA") as canvas:
                canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(canvas)
                
                # --- 1. Typography (Maxified for readability) ---
                try:
                    f_title = ImageFont.truetype(self.font_path if self.font_path else "arial", 48)
                    f_id = ImageFont.truetype(self.font_path if self.font_path else "arial", 32)
                    f_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 38)
                except:
                    f_title = f_id = f_content = ImageFont.load_default()

                # Pagination (Lower Technical Area)
                p_text = f"FED-DB // PAGE {page} OF {total_pages}"
                draw.text((CANVAS_W - 400, CANVAS_H - 110), p_text, fill=(180, 180, 255, 200), font=f_id)
                
                # --- 2. Dynamic Vertical Distribution ---
                display_items = items[:4]
                count = len(display_items)
                if count == 0: return self._empty_b64()

                # Calculate height per item
                item_h = CONTENT_H_TOTAL // count
                spacing = 20
                
                labels = ["1A", "1B", "2A", "2B"]
                
                for i, item in enumerate(display_items):
                    curr_y = CONTENT_T + (i * item_h)
                    self._draw_mega_slot(
                        canvas, 
                        item, 
                        (CONTENT_L, curr_y), 
                        CONTENT_W, 
                        item_h - spacing, 
                        labels[i], 
                        f_title, f_id, f_content
                    )

                buffered = BytesIO()
                canvas.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Renderer] Render critical failure: {e}")
            return ""

    def _draw_mega_slot(self, canvas, item, pos, w, h, item_id, f_t, f_id, f_c):
        """High-density vertical slot renderer."""
        draw = ImageDraw.Draw(canvas)
        title = (item.get("title") or "TECHNICAL DATA STREAM").upper()
        content = item.get("content", "").strip()
        img_raw = item.get("image_b64") or item.get("image_path")
        
        # --- A. Header Area ---
        # Large ID Tag
        draw.text((pos[0] + 10, pos[1] + 5), item_id, fill=(255, 170, 0, 255), font=f_id)
        # Bold Title
        draw.text((pos[0] + 120, pos[1] + 5), title, fill=(200, 200, 255, 255), font=f_id)
        
        # Thick LCARS Separator
        line_y = pos[1] + 60
        draw.rectangle([pos[0], line_y, pos[0] + w, line_y + 4], fill=(150, 150, 255, 120))
        
        # --- B. Content Body ---
        if img_raw:
            # FRAME + IMAGE MODE
            self._draw_stretched_brackets(canvas, pos, w, h)
            try:
                if item.get("image_b64"):
                    img = Image.open(BytesIO(base64.b64decode(item["image_b64"]))).convert("RGBA")
                else:
                    img = Image.open(img_raw).convert("RGBA")
                
                img.thumbnail((w - 120, h - 180), Image.Resampling.LANCZOS)
                ix = pos[0] + (w - img.width) // 2
                iy = pos[1] + (h - img.height) // 2 + 30
                canvas.alpha_composite(img, (ix, iy))
            except: pass
        else:
            # FULL WIDTH TEXT MODE
            text_y = pos[1] + 110
            wrap_w = w - 60
            lines = self._wrap_text_clean(content, f_c, wrap_w)
            for line in lines:
                if text_y + 50 > pos[1] + h - 10: break
                draw.text((pos[0] + 30, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                text_y += 50

    def _draw_stretched_brackets(self, canvas, pos, w, h):
        """Stretches brackets to match full content width."""
        try:
            with Image.open(self.frame_left).convert("RGBA") as f_l, \
                 Image.open(self.frame_right).convert("RGBA") as f_r:
                sh = h / f_l.height
                lw, rw = int(f_l.width * sh), int(f_r.width * sh)
                f_l_s = f_l.resize((lw, h), Image.Resampling.LANCZOS)
                f_r_s = f_r.resize((rw, h), Image.Resampling.LANCZOS)
                
                # Stretch Middle Body
                mid_w = w - lw - rw
                if mid_w > 0:
                    mid_slice = f_l_s.crop((lw-10, 0, lw-2, h)) # Wider slice for stability
                    mid_body = mid_slice.resize((mid_w, h), Image.Resampling.NEAREST)
                    canvas.alpha_composite(mid_body, (pos[0] + lw, pos[1]))
                
                canvas.alpha_composite(f_l_s, pos)
                canvas.alpha_composite(f_r_s, (pos[0] + w - rw, pos[1]))
        except: pass

    def _wrap_text_clean(self, text, font, max_width):
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

    def _empty_b64(self) -> str:
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        # Default constructor uses relative paths suitable for Docker environment
        _renderer = LCARS_Renderer()
    return _renderer

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
CONTENT_L = 340  # Tightened safely to the sidebar
CONTENT_T = 160
CONTENT_W = 1220 # Maximized breadth
CONTENT_B = 880
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
                
                # --- 1. Typography ---
                try:
                    f_title = ImageFont.truetype(self.font_path if self.font_path else "arial", 46)
                    f_id = ImageFont.truetype(self.font_path if self.font_path else "arial", 30)
                    f_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 36)
                except:
                    f_title = f_id = f_content = ImageFont.load_default()

                # Pagination
                p_text = f"FED-DB // PAGE {page} OF {total_pages}"
                draw.text((CANVAS_W - 400, CANVAS_H - 100), p_text, fill=(180, 180, 255, 180), font=f_id)
                
                # --- 2. Distribution ---
                display_items = items[:4]
                count = len(display_items)
                if count == 0: return self._empty_b64()

                item_h = CONTENT_H_TOTAL // count
                spacing = 25
                
                labels = ["1A", "1B", "2A", "2B"]
                for i, item in enumerate(display_items):
                    curr_y = CONTENT_T + (i * item_h)
                    self._draw_mega_slot(canvas, item, (CONTENT_L, curr_y), CONTENT_W, item_h - spacing, labels[i], f_title, f_id, f_content)

                buffered = BytesIO()
                canvas.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Renderer] Render critical failure: {e}")
            return ""

    def _draw_mega_slot(self, canvas, item, pos, w, h, item_id, f_t, f_id, f_c):
        draw = ImageDraw.Draw(canvas)
        title = (item.get("title") or "TECHNICAL DATA STREAM").upper()
        content = item.get("content", "").strip()
        img_raw = item.get("image_b64") or item.get("image_path")
        
        # Header
        draw.text((pos[0] + 15, pos[1] + 5), item_id, fill=(255, 170, 0, 255), font=f_id)
        draw.text((pos[0] + 120, pos[1] + 5), title, fill=(200, 200, 255, 255), font=f_id)
        
        line_y = pos[1] + 62
        draw.rectangle([pos[0], line_y, pos[0] + w, line_y + 4], fill=(150, 150, 255, 100))
        
        if img_raw:
            self._draw_stretched_brackets(canvas, pos, w, h)
            try:
                img = Image.open(BytesIO(base64.b64decode(item["image_b64"])) if item.get("image_b64") else img_raw).convert("RGBA")
                img.thumbnail((w - 120, h - 180), Image.Resampling.LANCZOS)
                canvas.alpha_composite(img, (pos[0] + (w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except: pass
        else:
            # TEXT MODE with Paragraph support
            text_y = pos[1] + 115
            line_height = 58 # 36pt + leading
            para_spacing = 20
            wrap_w = w - 60
            
            paragraphs = content.split('\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    text_y += para_spacing
                    continue
                
                lines = self._wrap_text_clean(para, f_c, wrap_w)
                for line in lines:
                    if text_y + line_height > pos[1] + h - 10: break
                    draw.text((pos[0] + 30, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                    text_y += line_height
                text_y += para_spacing # Gap between paragraphs

    def _draw_stretched_brackets(self, canvas, pos, w, h):
        try:
            with Image.open(self.frame_left).convert("RGBA") as f_l, \
                 Image.open(self.frame_right).convert("RGBA") as f_r:
                sh = h / f_l.height
                lw, rw = int(f_l.width * sh), int(f_r.width * sh)
                f_l_s, f_r_s = f_l.resize((lw, h), Image.Resampling.LANCZOS), f_r.resize((rw, h), Image.Resampling.LANCZOS)
                mid_w = w - lw - rw
                if mid_w > 0:
                    mid_body = f_l_s.crop((lw-10, 0, lw-2, h)).resize((mid_w, h), Image.Resampling.NEAREST)
                    canvas.alpha_composite(mid_body, (pos[0] + lw, pos[1]))
                canvas.alpha_composite(f_l_s, pos)
                canvas.alpha_composite(f_r_s, (pos[0] + w - rw, pos[1]))
        except: pass

    def _wrap_text_clean(self, text, font, max_width):
        if not text: return []
        lines, curr = [], ""
        for char in text:
            test = curr + char
            if font.getlength(test) <= max_width: curr = test
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

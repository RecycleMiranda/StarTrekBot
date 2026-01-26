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
        
        # Robust Font Discovery
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "arial.ttf"
        ]
        self.font_path = next((f for f in font_candidates if os.path.exists(f)), None)

    def split_content_to_pages(self, item: Dict, max_h: int = None) -> List[Dict]:
        """Splits a single technical record into multiple LCARS pages if it exceeds height."""
        if not max_h: max_h = CONTENT_H_TOTAL - 120 # Padding for header/lines
        
        try:
            f_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 24)
        except:
            f_content = ImageFont.load_default()
            
        line_height = 34
        para_spacing = 15
        wrap_w = CONTENT_W - 60
        
        paragraphs = (item.get("content") or "").strip().split('\n')
        pages = []
        current_page_text = []
        current_h = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                if current_h + para_spacing <= max_h:
                    current_page_text.append("")
                    current_h += para_spacing
                continue
                
            sentences = self._split_sentences(para)
            for sentence in sentences:
                lines = self._wrap_text_clean(sentence, f_content, wrap_w)
                needed_h = len(lines) * line_height + 5 # +5 inter-sentence
                
                if current_h + needed_h > max_h:
                    # Flush current page
                    pages.append({
                        "title": item.get("title", "TECHNICAL DATA"),
                        "content": "\n".join(current_page_text),
                        "image_b64": item.get("image_b64") if len(pages) == 0 else None # Only first page has image
                    })
                    current_page_text = ["(CONTINUED FROM PREVIOUS PAGE)", "", sentence]
                    current_h = (3 * line_height) + needed_h
                else:
                    current_page_text.append(sentence)
                    current_h += needed_h
            
            current_page_text.append("") # Para break
            current_h += para_spacing

        if current_page_text:
            pages.append({
                "title": item.get("title", "TECHNICAL DATA"),
                "content": "\n".join(current_page_text),
                "image_b64": item.get("image_b64") if len(pages) == 0 else None
            })
            
        return pages

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1) -> str:
        """Renders items using a Dynamic Vertical List to maximize UI space."""
        if not os.path.exists(self.bg_path):
            logger.error(f"[Renderer] Background not found: {self.bg_path}")
            raise FileNotFoundError(f"Background not found: {self.bg_path}")

        try:
            with Image.open(self.bg_path).convert("RGBA") as canvas:
                canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(canvas)
                
                # --- 1. Typography (Density Optimized) ---
                try:
                    f_title = ImageFont.truetype(self.font_path if self.font_path else "arial", 38)
                    f_id = ImageFont.truetype(self.font_path if self.font_path else "arial", 26)
                    f_content = ImageFont.truetype(self.font_path if self.font_path else "arial", 24)
                except:
                    f_title = f_id = f_content = ImageFont.load_default()

                # Pagination
                p_text = f"FED-DB // PAGE {page} OF {total_pages}"
                draw.text((CANVAS_W - 400, CANVAS_H - 100), p_text, fill=(180, 180, 255, 180), font=f_id)
                
                # --- 2. Distribution ---
                display_count = len(items)
                if display_count == 0: return self._empty_b64()

                item_h = CONTENT_H_TOTAL // display_count
                spacing = 25
                
                labels = ["1A", "1B", "2A", "2B"]
                for i, item in enumerate(items):
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
        
        line_y = pos[1] + 55
        draw.rectangle([pos[0], line_y, pos[0] + w, line_y + 4], fill=(150, 150, 255, 80))
        
        if img_raw and content:
            # --- HYBRID MODE (Image Left, Text Right) ---
            img_w = int(w * 0.45)
            text_l = pos[0] + img_w + 40
            text_w = w - img_w - 60
            
            # 1. Render Bracketed Image on Left
            self._draw_stretched_brackets(canvas, (pos[0], pos[1]), img_w, h)
            try:
                img_data = base64.b64decode(item["image_b64"]) if item.get("image_b64") else open(img_raw, "rb").read()
                img = Image.open(BytesIO(img_data)).convert("RGBA")
                img.thumbnail((img_w - 80, h - 160), Image.Resampling.LANCZOS)
                canvas.alpha_composite(img, (pos[0] + (img_w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except Exception as e:
                logger.warning(f"[Renderer] Hybrid image fail: {e}")

            # 2. Render Technical Text on Right
            text_y = pos[1] + 90
            line_h = 32
            para_s = 10
            
            paragraphs = content.split('\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    text_y += para_s
                    continue
                sentences = self._split_sentences(para)
                for sentence in sentences:
                    lines = self._wrap_text_clean(sentence, f_c, text_w)
                    if text_y + (len(lines) * line_h) > pos[1] + h - 10: break
                    for line in lines:
                        draw.text((text_l, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                        text_y += line_h
                    text_y += 4
                text_y += para_s
                
        elif img_raw:
            # --- IMAGE ONLY MODE ---
            self._draw_stretched_brackets(canvas, pos, w, h)
            try:
                img_data = base64.b64decode(item["image_b64"]) if item.get("image_b64") else open(img_raw, "rb").read()
                img = Image.open(BytesIO(img_data)).convert("RGBA")
                img.thumbnail((w - 120, h - 180), Image.Resampling.LANCZOS)
                canvas.alpha_composite(img, (pos[0] + (w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except: pass
        else:
            # --- TEXT ONLY MODE ---
            text_y = pos[1] + 90
            line_height = 34
            para_spacing = 15
            wrap_w = w - 60
            
            paragraphs = content.split('\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    text_y += para_spacing
                    continue
                
                sentences = self._split_sentences(para)
                for sentence in sentences:
                    lines = self._wrap_text_clean(sentence, f_c, wrap_w)
                    needed_h = len(lines) * line_height
                    if text_y + needed_h > pos[1] + h - 10: return 
                    
                    for line in lines:
                        draw.text((pos[0] + 30, text_y), line, fill=(255, 255, 255, 255), font=f_c)
                        text_y += line_height
                    text_y += 5 
                text_y += para_spacing # Gap between paragraphs

    def _split_sentences(self, text):
        import re
        # Basic sentence splitting (simplified for LCARS context)
        # Splits by period/exclamation/question followed by space or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _draw_stretched_brackets(self, canvas, pos, w, h):
        try:
            with Image.open(self.frame_left).convert("RGBA") as f_l, \
                 Image.open(self.frame_right).convert("RGBA") as f_r:
                sh = h / f_l.height
                lw, rw = int(f_l.width * sh), int(f_r.width * sh)
                f_l_s, f_r_s = f_l.resize((lw, h), Image.Resampling.LANCZOS), f_r.resize((rw, h), Image.Resampling.LANCZOS)
                mid_w = w - lw - rw
                if mid_w > 0:
                    mid_slice = f_l_s.crop((lw-10, 0, lw-2, h))
                    mid_body = mid_slice.resize((mid_w, h), Image.Resampling.NEAREST)
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

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        # Default constructor uses relative paths suitable for Docker environment
        _renderer = LCARS_Renderer()
    return _renderer

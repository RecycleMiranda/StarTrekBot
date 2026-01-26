import os
import base64
import logging
import re
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

# Metric Constants
LINE_HEIGHT = 26     # Aggressive compression for high density
PARA_SPACING = 12    # Clear paragraph separation
FONT_SIZE = 24

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
        
        # Custom Local Fonts
        app_dir = os.path.dirname(__file__)
        self.font_dir = os.path.join(app_dir, "static", "assets", "fonts")
        self.lcars_font = os.path.join(self.font_dir, "lcars.ttf")
        self.chinese_font = os.path.join(self.font_dir, "No.67-ShangShouXuanSongTi-2.ttf")
        
        # Fallback fonts
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "arial.ttf"
        ]
        self.fallback_font = next((f for f in font_candidates if os.path.exists(f)), "arial.ttf")

    def get_font(self, text: str, size: int):
        """Returns the appropriate font object based on content language."""
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
        target_path = self.chinese_font if is_chinese and os.path.exists(self.chinese_font) else self.lcars_font
        
        if not os.path.exists(target_path):
            target_path = self.fallback_font
            
        try:
            return ImageFont.truetype(target_path, size)
        except:
            return ImageFont.load_default()

    def split_content_to_pages(self, item: Dict, max_h: int = None) -> List[Dict]:
        """Splits a single technical record into multiple LCARS pages if it exceeds height."""
        if not max_h: max_h = CONTENT_H_TOTAL - 120 
        
        content = item.get("content", "")
        # Programmatic prefix removal
        content = re.sub(r'\[(EN|ZH|Standard|Chinese)\]:?\s*', '', content, flags=re.IGNORECASE)
        
        wrap_w = CONTENT_W - 60
        
        pages = []
        current_page_content = []
        current_h = 0
        
        paragraphs = content.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                current_h += PARA_SPACING + 5 
                continue
            
            # Metric calculation based on full paragraph
            f_c = self.get_font(para, FONT_SIZE)
            lines = self._wrap_text_clean(para, f_c, wrap_w)
            needed_h = len(lines) * LINE_HEIGHT
            
            if current_h + needed_h > max_h:
                pages.append({
                    "title": item.get("title", "TECHNICAL DATA"),
                    "content": "\n\n".join([c for c in current_page_content if c]),
                    "image_b64": item.get("image_b64") if len(pages) == 0 else None
                })
                current_page_content = ["(CONTINUED FROM PREVIOUS PAGE)", "", para]
                current_h = (3 * LINE_HEIGHT) + needed_h + PARA_SPACING
            else:
                current_page_content.append(para)
                current_h += needed_h + PARA_SPACING

        if any(c.strip() for c in current_page_content):
            pages.append({
                "title": item.get("title", "TECHNICAL DATA"),
                "content": "\n".join([c for c in current_page_content if c or c == ""]),
                "image_b64": item.get("image_b64") if len(pages) == 0 else None
            })
            
        return pages

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1) -> str:
        """Renders items using a Dynamic Vertical List to maximize UI space."""
        if not os.path.exists(self.bg_path):
            logger.error(f"[Renderer] Background not found: {self.bg_path}")
            return self._empty_b64()

        try:
            with Image.open(self.bg_path).convert("RGBA") as canvas:
                canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(canvas)
                
                f_title = self.get_font("TITLE", 38)
                f_id = self.get_font("ID", 26)
                
                p_text = f"FED-DB // PAGE {page} OF {total_pages}"
                draw.text((CANVAS_W - 400, CANVAS_H - 100), p_text, fill=(180, 180, 255, 180), font=f_id)
                
                display_count = len(items)
                if display_count == 0: return self._empty_b64()

                item_h = CONTENT_H_TOTAL // display_count
                spacing = 25
                labels = ["1A", "1B", "2A", "2B"]
                
                for i, item in enumerate(items):
                    curr_y = CONTENT_T + (i * item_h)
                    self._draw_mega_slot(canvas, item, (CONTENT_L, curr_y), CONTENT_W, item_h - spacing, labels[i], f_title, f_id)

                buffered = BytesIO()
                canvas.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Renderer] Render critical failure: {e}")
            return self._empty_b64()

    def _draw_mega_slot(self, canvas, item, pos, w, h, item_id, f_t, f_id):
        draw = ImageDraw.Draw(canvas)
        title = (item.get("title") or "TECHNICAL DATA STREAM").upper()
        content = item.get("content", "").strip()
        img_b64 = item.get("image_b64")
        
        draw.text((pos[0] + 15, pos[1] + 5), item_id, fill=(255, 170, 0, 255), font=f_id)
        draw.text((pos[0] + 120, pos[1] + 5), title, fill=(200, 200, 255, 255), font=f_id)
        
        line_y = pos[1] + 55
        draw.rectangle([pos[0], line_y, pos[0] + w, line_y + 4], fill=(150, 150, 255, 80))
        
        if img_b64 and content:
            img_w = int(w * 0.45)
            text_l = pos[0] + img_w + 40
            text_w = w - img_w - 60
            self._draw_stretched_brackets(canvas, (pos[0], pos[1]), img_w, h)
            try:
                img_data = base64.b64decode(img_b64)
                with Image.open(BytesIO(img_data)).convert("RGBA") as img:
                    img.thumbnail((img_w - 80, h - 160), Image.Resampling.LANCZOS)
                    canvas.alpha_composite(img, (pos[0] + (img_w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except Exception as e:
                logger.warning(f"[Renderer] Hybrid image fail: {e}")

            text_y = pos[1] + 65 # Tightened top margin
            paragraphs = content.split('\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    text_y += PARA_SPACING
                    continue
                
                # Render full paragraph as a block
                f_line = self.get_font(para, FONT_SIZE)
                lines = self._wrap_text_clean(para, f_line, text_w)
                
                if text_y + (len(lines) * LINE_HEIGHT) > pos[1] + h - 10: break
                
                for line in lines:
                    draw.text((text_l, text_y), line, fill=(255, 255, 255, 255), font=f_line)
                    text_y += LINE_HEIGHT # Tighter leading
                
                text_y += PARA_SPACING # Paragraph spacing
        elif img_b64:
            self._draw_stretched_brackets(canvas, pos, w, h)
            try:
                img_data = base64.b64decode(img_b64)
                with Image.open(BytesIO(img_data)).convert("RGBA") as img:
                    img.thumbnail((w - 120, h - 180), Image.Resampling.LANCZOS)
                    canvas.alpha_composite(img, (pos[0] + (w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except: pass
        else:
            text_y = pos[1] + 65 # Tightened top margin
            paragraphs = content.split('\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    text_y += PARA_SPACING
                    continue
                
                # Render full paragraph as a block
                f_line = self.get_font(para, FONT_SIZE)
                lines = self._wrap_text_clean(para, f_line, w - 60)
                
                if text_y + (len(lines) * LINE_HEIGHT) > pos[1] + h - 10: return
                
                for line in lines:
                    draw.text((pos[0] + 30, text_y), line, fill=(255, 255, 255, 255), font=f_line)
                    text_y += LINE_HEIGHT # Tighter leading
                
                text_y += PARA_SPACING # Paragraph spacing

    def _split_sentences(self, text):
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

    def _draw_stretched_brackets(self, canvas, pos, w, h):
        try:
            with Image.open(self.frame_left).convert("RGBA") as f_l, \
                 Image.open(self.frame_right).convert("RGBA") as f_r:
                sh = h / f_l.height
                lw, rw = int(f_l.width * sh), int(f_r.width * sh)
                f_l_s = f_l.resize((lw, h), Image.Resampling.LANCZOS)
                f_r_s = f_r.resize((rw, h), Image.Resampling.LANCZOS)
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
        _renderer = LCARS_Renderer()
    return _renderer

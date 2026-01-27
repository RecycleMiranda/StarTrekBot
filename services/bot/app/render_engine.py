import os
import base64
import logging
import re
import json
import math
from io import BytesIO
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Target working resolution
CANVAS_W = 1600
CANVAS_H = 960

# FINAL COORDINATE DEFINITIONS
CONTENT_L = 340  
CONTENT_T = 160
CONTENT_W = 1220 
CONTENT_B = 880
CONTENT_H_TOTAL = CONTENT_B - CONTENT_T

# Metric Constants
LINE_HEIGHT = 28     
PARA_SPACING = 15     
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
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "arial.ttf",
             self.lcars_font
        ]
        self.fallback_font = next((f for f in font_candidates if os.path.exists(f)), "arial.ttf")

    def get_font(self, text: str, size: int):
        """Returns the appropriate font object based on content language."""
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in str(text)) if text else False
        target_path = self.chinese_font if is_chinese and os.path.exists(self.chinese_font) else self.lcars_font
        
        if not os.path.exists(target_path):
            target_path = self.fallback_font
            
        try:
            return ImageFont.truetype(target_path, size)
        except:
            return ImageFont.load_default()

    def split_content_to_pages(self, item: Dict, max_h: int = None) -> List[Dict]:
        """Splits a single technical record into multiple LCARS pages if it exceeds height."""
        # 1. Handle Blueprint bypass (Phase 7.5 Fix)
        if item.get("type") == "blueprint":
            return [item]
        
        if not max_h: max_h = CONTENT_H_TOTAL - 220 
        
        content = item.get("content", "")
        # Beacon Protocol (Surgical Strike)
        if "^^DATA_START^^" in content:
            content = content.split("^^DATA_START^^")[-1].strip()
            
        # Programmatic prefix removal
        content = re.sub(r'\[(EN|ZH|Standard|Chinese|Source|Translation)\]:?\s*', '', content, flags=re.IGNORECASE)
        
        # AGGRESSIVE NORMALIZATION: Merge fragmented lines into paragraphs
        content = self._normalize_text_flow(content)
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        
        # GLOBAL HEADER EXTRACTION
        base_title = item.get("title", "TECHNICAL DATA STREAM")
        
        pages = []
        current_page_paras = []
        
        def get_page_h(paras):
            if not paras: return 0
            # Rough estimate for text blocks
            return len(paras) * (LINE_HEIGHT + PARA_SPACING)

        for para in paragraphs:
            test_paras = current_page_paras + [para]
            if get_page_h(test_paras) > max_h:
                if current_page_paras:
                    pages.append({
                        "title": base_title,
                        "content": "\n".join(current_page_paras),
                        "image_b64": item.get("image_b64") if len(pages) == 0 else None,
                        "source": item.get("source", "UNKNOWN")
                    })
                current_page_paras = [para]
            else:
                current_page_paras.append(para)

        if current_page_paras:
            pages.append({
                "title": base_title,
                "content": "\n".join(current_page_paras),
                "image_b64": item.get("image_b64") if len(pages) == 0 else None,
                "source": item.get("source", "UNKNOWN")
            })
            
        return pages

    def render_report(self, items: List[Dict], page: int = 1, total_pages: int = 1, active_node: str = "COORDINATOR", audit_status: str = "NOMINAL", integrity_status: str = "OPTIMAL") -> str:
        """Main rendering entry point."""
        try:
            if os.path.exists(self.bg_path):
                bg_img = Image.open(self.bg_path).convert("RGBA")
            else:
                bg_img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (5, 5, 25, 255))
                
            with bg_img as canvas:
                canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(canvas)
                
                # Pagination
                if total_pages > 1:
                    f_id = self.get_font("ID", 26)
                    p_text = f"FED-DB // PAGE {page} OF {total_pages}"
                    draw.text((CANVAS_W - 400, CANVAS_H - 100), p_text, fill=(180, 180, 255, 180), font=f_id)

                if len(items) == 1 and items[0].get("type") == "blueprint":
                    self._render_blueprint(canvas, draw, items[0])
                else:
                    self._render_multi_slot(canvas, draw, items)

                buffered = BytesIO()
                canvas.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Renderer] Render failure: {e}")
            return self._empty_b64()

    def _render_multi_slot(self, canvas: Image, draw: ImageDraw, items: List[Dict]):
        display_count = len(items)
        if display_count == 0: return

        item_h = CONTENT_H_TOTAL // display_count
        spacing = 25
        labels = ["1A", "1B", "2A", "2B"]
        curr_y = CONTENT_T 
        
        f_title = self.get_font("TITLE", 38)
        f_id = self.get_font("ID", 26)

        for i, item in enumerate(items):
            is_list = (display_count > 1)
            self._draw_mega_slot(canvas, item, (CONTENT_L, curr_y), CONTENT_W, item_h - spacing, labels[i], f_title, f_id, is_list=is_list)
            curr_y += item_h

    def _render_blueprint(self, canvas: Image, draw: ImageDraw, item: Dict):
        """Core JSON Blueprint Rasterizer (Full Page)."""
        header = item.get("header", {})
        layout = item.get("layout", [])
        
        # 1. Main Header
        self._draw_main_header(draw, header)
        
        # 2. Layout Blocks
        curr_y = CONTENT_T + 60
        curr_x = CONTENT_L
        
        for block in layout:
            b_type = block.get("type")
            if b_type == "kv_grid":
                curr_y = self._draw_kv_grid(draw, block, curr_x, curr_y)
            elif b_type == "text_block":
                curr_y = self._draw_text_block(draw, block, curr_x, curr_y)
            elif b_type == "section_header":
                curr_y = self._draw_section_header(draw, block, curr_x, curr_y)
            elif b_type == "bullet_list":
                curr_y = self._draw_bullet_list(draw, block, curr_x, curr_y)
            curr_y += PARA_SPACING

    def _draw_main_header(self, draw: ImageDraw, header: Dict):
        title_en = header.get("title_en", "UNKNOWN")
        title_cn = header.get("title_cn", "")
        f_en = self.get_font(title_en, 50)
        # Shifted down to avoid overlapping with top curves
        draw.text((360, 65), title_en.upper(), fill=(255, 153, 0), font=f_en)
        if title_cn:
            f_cn = self.get_font(title_cn, 30)
            draw.text((360, 115), title_cn, fill=(255, 200, 100), font=f_cn)

    def _draw_kv_grid(self, draw: ImageDraw, block: Dict, x: int, y: int) -> int:
        cols = block.get("cols", 1)
        data = block.get("data", [])
        if not data: return y
        col_w = (CONTENT_W - (cols-1)*20) // cols
        row_h = 36
        total_rows = math.ceil(len(data) / cols)
        font_k = self.get_font("K", 22)
        font_v = self.get_font("V", 22)
        for i, item in enumerate(data):
            row = i // cols
            col = i % cols
            item_x = x + col * (col_w + 20)
            item_y = y + row * row_h
            if row % 2 == 0:
                draw.rectangle([item_x, item_y, item_x + col_w, item_y + row_h - 4], fill=(100, 150, 255, 40))
            draw.text((item_x + 10, item_y + 4), str(item.get("k", "")).upper(), fill=(153, 204, 255), font=font_k)
            v_text = str(item.get("v", ""))
            v_w = font_v.getlength(v_text)
            draw.text((item_x + col_w - v_w - 10, item_y + 4), v_text, fill=(255, 255, 255), font=font_v)
        return y + (total_rows * row_h) + 10

    def _draw_text_block(self, draw: ImageDraw, block: Dict, x: int, y: int) -> int:
        content = block.get("content", "")
        if not content: return y
        font = self.get_font(content, 26)
        lines = self._wrap_text_clean(content, font, CONTENT_W)
        lh = 34
        for line in lines:
            draw.text((x, y), line, fill=(255, 255, 255), font=font)
            y += lh
        return y + 10

    def _draw_section_header(self, draw: ImageDraw, block: Dict, x: int, y: int) -> int:
        title = block.get("title_en", "").upper()
        if block.get("title_cn"): title += f" {block.get('title_cn')}"
        font = self.get_font(title, 32)
        draw.text((x, y + 10), title, fill=(255, 153, 0), font=font)
        draw.rectangle([x, y + 45, x + 300, y + 48], fill=(255, 153, 0))
        return y + 60

    def _draw_bullet_list(self, draw: ImageDraw, block: Dict, x: int, y: int) -> int:
        items = block.get("items", [])
        font = self.get_font("List", 26)
        lh = 34
        for item in items:
            draw.text((x + 20, y), f"\u2022  {item}", fill=(200, 220, 255), font=font)
            y += lh
        return y + 10

    def _draw_mega_slot(self, canvas, item, pos, w, h, item_id, f_t, f_id, is_list=True):
        draw = ImageDraw.Draw(canvas)
        raw_title = (item.get("title") or "TECHNICAL DATA STREAM").strip()
        title_parts = [p.strip() for p in raw_title.split('\n') if p.strip()]
        title_en = title_parts[0] if title_parts else "TECHNICAL DATA"
        title_zh = title_parts[1] if len(title_parts) > 1 else ""
        content = item.get("content", "").strip()
        content = self._normalize_text_flow(content)

        f_title_en = self.get_font(title_en, 56)
        f_title_zh = self.get_font(title_zh, 32)
        f_id_large = self.get_font("ID", 32)
        f_id_small = self.get_font("ID", 20)

        source = item.get("source", "UNKNOWN")
        badge_text = f"// VERIFIED SOURCE: {source.upper()}"
        badge_w = draw.textlength(badge_text, font=f_id_small)
        
        header_y = pos[1] + 35
        draw.text((pos[0] + 15, header_y + 5), item_id, fill=(255, 170, 0, 255), font=f_id_large)
        draw.text((pos[0] + 90, header_y), title_en, fill=(255, 180, 50, 255), font=f_title_en)
        if title_zh:
            draw.text((pos[0] + 95, header_y + 60), title_zh, fill=(180, 180, 255, 200), font=f_title_zh)
        draw.text((pos[0] + w - badge_w - 20, header_y - 20), badge_text, fill=(0, 255, 120, 150), font=f_id_small)
        
        divider_y = pos[1] + 135
        draw.rectangle([pos[0], divider_y, pos[0] + w, divider_y + 2], fill=(150, 150, 255, 60))
        
        text_y = pos[1] + 175 
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        for i, para in enumerate(paragraphs):
            f_line = self.get_font(para, FONT_SIZE)
            lines = self._wrap_text_clean(para, f_line, w - 60)
            if text_y + (len(lines) * LINE_HEIGHT) > pos[1] + h - 10: break
            color = self._get_color_for_text(para, index=i, is_list=is_list)
            for line in lines:
                draw.text((pos[0] + 30, text_y), line, fill=color, font=f_line)
                text_y += LINE_HEIGHT 
            text_y += PARA_SPACING 

    def _wrap_text_clean(self, text, font, max_width):
        if not text: return []
        lines, curr = [], ""
        for char in str(text):
            test = curr + char
            if font.getlength(test) <= max_width: curr = test
            else:
                if curr: lines.append(curr)
                curr = char
        if curr: lines.append(curr)
        return lines

    def _normalize_text_flow(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        raw_blocks = re.split(r'\n\s*\n', text)
        normalized_blocks = []
        for block in raw_blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines: continue
            merged = " ".join(lines)
            normalized_blocks.append(merged)
        result = "\n\n".join(normalized_blocks)
        return result.replace("**", "").replace("*", "")

    def _get_color_for_text(self, text: str, index: int = 0, is_list: bool = True) -> Tuple[int, int, int, int]:
        is_alt = (index % 2 == 1) and is_list
        if re.search(r'[\u4e00-\u9fff]', str(text)):
            return (150, 180, 255, 255) if not is_alt else (100, 150, 255, 200)
        else:
            return (245, 245, 255, 255) if not is_alt else (200, 200, 255, 200)

    def _empty_b64(self) -> str:
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,255))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

_renderer = None
def get_renderer():
    global _renderer
    if not _renderer:
        _renderer = LCARS_Renderer()
    return _renderer

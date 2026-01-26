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
LINE_HEIGHT = 28     # Balanced for multi-font blocks
PARA_SPACING = 6     # Tightened for bilingual density
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
        
        # COLUMNAR DETECTOR (Universal)
        avg_len = (sum(len(p) for p in paragraphs) / len(paragraphs)) if paragraphs else 0
        if len(paragraphs) > 15 and avg_len < 45:
            num_cols = 3
        elif len(paragraphs) > 8 and avg_len < 60:
            num_cols = 2
        else:
            num_cols = 1
        
        pages = []
        current_page_paras = []
        
        # Capacity logic matches _draw_mega_slot
        def get_page_h(paras, cols):
            if not paras: return 0
            rows = (len(paras) + cols - 1) // cols
            # Columnar items are now double-lined (EN + subsidiary ZH)
            lh_factor = 1.8 if cols > 1 else 1.0
            return int(rows * (LINE_HEIGHT * lh_factor + PARA_SPACING // 4))

        for para in paragraphs:
            test_paras = current_page_paras + [para]
            if get_page_h(test_paras, num_cols) > max_h:
                if current_page_paras:
                    pages.append({
                        "title": item.get("title", "TECHNICAL DATA"),
                        "content": "\n".join(current_page_paras),
                        "image_b64": item.get("image_b64") if len(pages) == 0 else None,
                        "source": item.get("source", "UNKNOWN")
                    })
                current_page_paras = [para]
            else:
                current_page_paras.append(para)

        if current_page_paras:
            pages.append({
                "title": item.get("title", "TECHNICAL DATA"),
                "content": "\n".join(current_page_paras),
                "image_b64": item.get("image_b64") if len(pages) == 0 else None,
                "source": item.get("source", "UNKNOWN")
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
                
                # Conditional Pagination: Hide if only one page exists
                if total_pages > 1:
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
        # DYNAMIC BILINGUAL HEADER
        raw_title = (item.get("title") or "TECHNICAL DATA STREAM").strip()
        title_parts = [p.strip() for p in raw_title.split('\n') if p.strip()]
        title_en = title_parts[0] if title_parts else "TECHNICAL DATA"
        title_zh = title_parts[1] if len(title_parts) > 1 else ""
        
        content = item.get("content", "").strip()
        
        # PHYSICAL TITLE STRIPPER (Critical Safety Net) & SUBTITLE PROMOTION
        # Removes LLM-hallucinated headers like "Starfleet Starship Classes"
        content_lines = content.split('\n')
        # Aggressive Header Consumption Loop (Max 3 lines)
        # Consumes lines that look like titles (short, no periods) to populate the main header
        consumed_count = 0
        while content_lines and consumed_count < 3:
            first_line = content_lines[0].strip()
            if not first_line: # Skip empty
                content_lines.pop(0)
                continue
                
            # Header Detection Heuristic: Short length, no ending period (unless it's a colon)
            is_header_like = len(first_line) < 60 and (not first_line.endswith(".") or first_line.endswith(":"))
            
            # Special case: If it's the very first line and matches known patterns
            cleaned = first_line.lower().replace(" ", "")
            is_known_pattern = any(x in cleaned for x in ["list", "captain", "class", "starship", "列表", "级别", "舰长", "summary"])
            
            if is_header_like or is_known_pattern:
                # Determine Language
                promoted = first_line.replace(":", "").replace("：", "").strip()
                if re.search(r'[\u4e00-\u9fff]', promoted):
                     # Chinese -> Subtitle
                     # Only start consuming if not already manually set, OR if we are overriding a generic default
                     if not title_zh or "联邦" in title_zh: 
                         title_zh = promoted
                else:
                     # English -> Main Title
                     # Always override "TECHNICAL DATA STREAM" if we find a specific English header
                     title_en = promoted
                
                content_lines.pop(0)
                consumed_count += 1
            else:
                break # Stop at first non-header line
                
        content = '\n'.join(content_lines).strip()
        
        content = self._normalize_text_flow(content)

        # RE-CALCULATE FONTS after potential promotion
        f_title_en = self.get_font(title_en, 80)
        f_title_zh = self.get_font(title_zh, 32)
        f_id_large = self.get_font("ID", 36)

        img_b64 = item.get("image_b64")
        
        # Draw ID and Leading English Title (Left Aligned)
        draw.text((pos[0] + 15, pos[1] + 15), item_id, fill=(255, 170, 0, 255), font=f_id_large)
        # Shifted English title to left, massive size
        draw.text((pos[0] + 80, pos[1] + 0), title_en, fill=(255, 180, 50, 255), font=f_title_en)
        
        # Sub-title (Chinese) with color differentiation - Tucked under English
        if title_zh:
            draw.text((pos[0] + 85, pos[1] + 68), title_zh, fill=(180, 180, 255, 200), font=f_title_zh)
        
        # SOURCE BADGE (Verification Layer)
        source = item.get("source", "UNKNOWN")
        badge_text = f"// VERIFIED SOURCE: {source}"
        badge_w = draw.textlength(badge_text, font=f_id)
        draw.text((pos[0] + w - badge_w - 30, pos[1] + 5), badge_text, fill=(0, 255, 100, 150), font=f_id)

        # Lower horizontal line to create absolute distance
        line_y = pos[1] + 140
        draw.rectangle([pos[0], line_y, pos[0] + w, line_y + 4], fill=(150, 150, 255, 80))
        
        if img_b64 and content:
            # ... (image remains same, but text_y adjusted)
            img_w = int(w * 0.45)
            text_l = pos[0] + img_w + 40
            text_w = w - img_w - 60
            self._draw_stretched_brackets(canvas, (pos[0], pos[1]), img_w, h)
            try:
                img_data = base64.b64decode(img_b64)
                with Image.open(BytesIO(img_data)).convert("RGBA") as img:
                    img.thumbnail((img_w - 80, h - 160), Image.Resampling.LANCZOS)
                    canvas.alpha_composite(img, (pos[0] + (img_w - img.width) // 2, pos[1] + (h - img.height) // 2 + 50))
            except Exception as e:
                logger.warning(f"[Renderer] Hybrid image fail: {e}")

            text_y = pos[1] + 160 # Jump below massive header
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            for i, para in enumerate(paragraphs):
                # Render full paragraph as a block
                f_line = self.get_font(para, FONT_SIZE)
                lines = self._wrap_text_clean(para, f_line, text_w)
                
                if text_y + (len(lines) * LINE_HEIGHT) > pos[1] + h - 10: break
                
                color = self._get_color_for_text(para, index=i)
                for line in lines:
                    draw.text((text_l, text_y), line, fill=color, font=f_line)
                    text_y += LINE_HEIGHT 
                
                text_y += PARA_SPACING 
        elif img_b64:
            self._draw_stretched_brackets(canvas, pos, w, h)
            try:
                img_data = base64.b64decode(img_b64)
                with Image.open(BytesIO(img_data)).convert("RGBA") as img:
                    img.thumbnail((w - 120, h - 180), Image.Resampling.LANCZOS)
                    canvas.alpha_composite(img, (pos[0] + (w - img.width) // 2, pos[1] + (h - img.height) // 2 + 35))
            except: pass
        else:
            text_y_start = pos[1] + 160 
            
            # DYNAMIC FONT SELECTION & COLUMN DETECTION
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            
            # Smart Columnar Protocol: Detect if we should use columns (Dense List Detection)
            avg_len = (sum(len(p) for p in paragraphs) / len(paragraphs)) if paragraphs else 0
            if len(paragraphs) > 15 and avg_len < 45:
                num_cols = 3
            elif len(paragraphs) > 8 and avg_len < 60:
                num_cols = 2
            else:
                num_cols = 1
                
            col_inner_spacing = 30 if num_cols == 3 else 50
            col_w = (w - 60 - (num_cols - 1) * col_inner_spacing) // num_cols
            
            # Dynamic Font Inflation logic (Enhanced for Massive Display)
            best_size = 40 # Baseline massively increased per user request
            best_lh = int(40 * 1.15)
            
            # Test sizes for best fit - up to 60pt
            for size in range(60, 27, -2):
                lh = int(size * 1.15)
                f_test = self.get_font(content, size)
                
                # Estimate height with columns (Double-line height for EN+ZH)
                lines_per_col = (len(paragraphs) + num_cols - 1) // num_cols
                est_h = (lines_per_col * (lh * 1.8)) + (lines_per_col * PARA_SPACING // 4)
                
                if est_h <= (h - 130):
                    best_size = size
                    best_lh = lh
                    break
            
            f_final = self.get_font(content, best_size)
            f_sub = self.get_font(content, int(best_size * 0.75)) # Smaller font for Chinese sub-line
            
            # Render across columns
            for i, para in enumerate(paragraphs):
                col_idx = i % num_cols
                row_idx = i // num_cols # Zebra by row
                
                # Check for bilingual split: Name (Chinese)
                match = re.search(r"^(.*?)\s*\((.*?)\)$", para)
                if match and num_cols > 1:
                    en_text, zh_text = match.groups()
                    sub_lh = int(best_lh * 0.8) # Spacing for sub-line
                else:
                    en_text, zh_text = para, ""
                    sub_lh = 0
                
                curr_x = pos[0] + 30 + (col_idx * (col_w + col_inner_spacing))
                # Total height per item: best_lh (English) + sub_lh (Chinese)
                item_full_h = best_lh + sub_lh + (PARA_SPACING // 4)
                curr_y = text_y_start + (row_idx * item_full_h)
                
                if curr_y + item_full_h > pos[1] + h - 10: break
                
                color_en = self._get_color_for_text(en_text, index=row_idx)
                
                # FONT ENFORCEMENT: Explicitly get font for English text to ensure LCARS
                # (Previous logic used f_final derived from whole content, which likely defaulted to Chinese font)
                f_en = self.get_font(en_text, best_size)
                
                # Render Primary (English)
                draw.text((curr_x, curr_y), en_text, fill=color_en, font=f_en)
                
                # Render Subsidiary (Chinese) below English, left aligned
                if zh_text:
                    color_zh = (150, 180, 255, 180) if (row_idx % 2 == 0) else (100, 150, 255, 150)
                    # Tighten spacing: distinct visual grouping
                    draw.text((curr_x, curr_y + int(best_size * 1.1)), zh_text, fill=color_zh, font=f_sub)

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

    def _normalize_text_flow(self, text: str) -> str:
        """
        Aggressively merges fragmented lines into cohesive paragraphs.
        Enforces 'English Block -> Chinese Block' logic.
        """
        if not text: return ""
        
        # Step 1: Normalize all newlines
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Step 2: Split by double newline (logical blocks/sections)
        raw_blocks = re.split(r'\n\s*\n', text)
        
        normalized_blocks = []
        for block in raw_blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines: continue
            
            merged_lines = []
            curr_accumulator = lines[0]
            
            for i in range(1, len(lines)):
                prev = lines[i-1]
                curr = lines[i]
                
                # Enhanced detection: If line contains Chinese and ends with ')', treat as CN/Bilingual end
                has_cn = bool(re.search(r'[\u4e00-\u9fff]', prev))
                
                prev_is_en = bool(re.search(r'[a-zA-Z0-9\.,:;!?\}\]\"\*\' ]$', prev)) # Removed ) from EN end if it might be CN
                curr_is_cn = bool(re.search(r'^[\*\s]*[\u4e00-\u9fff\（\【]', curr))
                
                prev_is_cn = bool(re.search(r'[\u4e00-\u9fff。！？\）\】\)\*]$', prev)) and (has_cn or not prev_is_en)
                curr_is_en = bool(re.search(r'^[\*\s]*[a-zA-Z0-9]', curr))
                
                if (prev_is_en and curr_is_cn) or (prev_is_cn and curr_is_en):
                    # BILINGUAL SPLIT: Save current accumulator and start new one
                    merged_lines.append(curr_accumulator)
                    curr_accumulator = curr
                else:
                    # MERGE: Handle spacing
                    if re.search(r'[a-zA-Z0-9\.,!?\*]$', prev) and re.search(r'^[\*\s]*[a-zA-Z0-9]', curr):
                        curr_accumulator += " " + curr
                    else:
                        curr_accumulator += curr
            
            merged_lines.append(curr_accumulator)
            normalized_blocks.append("\n".join(merged_lines))
        
        # Step 3: Strip remaining Markdown markers (Aggressive Cleanup)
        result = "\n\n".join(normalized_blocks)
        result = result.replace("**", "").replace("*", "")
        return result

    def _get_color_for_text(self, text: str, index: int = 0) -> Tuple[int, int, int, int]:
        """Returns LCARS color based on dominant language and row index for zebra-striping."""
        is_alt = (index % 2 == 1)
        # Detect Chinese characters
        if re.search(r'[\u4e00-\u9fff]', text):
            # LCARS Cyan-Blue for Chinese
            return (150, 180, 255, 255) if not is_alt else (100, 150, 255, 200)
        else:
            # Pure White for English/Technical Standard
            return (245, 245, 255, 255) if not is_alt else (200, 200, 255, 200)

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

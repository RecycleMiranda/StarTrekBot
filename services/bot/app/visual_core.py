import os
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# LCARS 2.0 (Picard) Color Palette - "Nemesis Blue"
COLOR_BG = (12, 18, 36) # Darker Navy
COLOR_FRAME = (32, 48, 96, 160) # Translucent Blue Frame
COLOR_ACCENT = (64, 128, 255) # Bright LCARS Blue
COLOR_TEXT = (255, 255, 255) # Pure White
COLOR_CATEGORY = (255, 150, 0) # LCARS Orange for Headers

class VisualCore:
    def __init__(self):
        # Font resolution - attempting to use a common sans-serif
        try:
            # Try to find a clean sans-serif font
            font_paths = [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "Arial.ttf"
            ]
            self.font_main = None
            for path in font_paths:
                if os.path.exists(path):
                    self.font_main = ImageFont.truetype(path, 20)
                    self.font_title = ImageFont.truetype(path, 32)
                    self.font_cat = ImageFont.truetype(path, 24)
                    break
            
            if not self.font_main:
                self.font_main = ImageFont.load_default()
                self.font_title = ImageFont.load_default()
                self.font_cat = ImageFont.load_default()
        except:
            self.font_main = ImageFont.load_default()
            self.font_title = ImageFont.load_default()
            self.font_cat = ImageFont.load_default()

    def render_report(self, report_data: Dict[str, Any]) -> io.BytesIO:
        """
        Renders a structured report into an LCARS 2.0 style image.
        """
        title = report_data.get("title", "LCARS STATUS REPORT").upper()
        sections = report_data.get("sections", [])

        # Calculate dynamic height
        # Base height (header) + sections (category + wrapped content) + footer
        width = 800
        padding = 40
        current_y = 120
        section_spacing = 30
        
        # Temporary image to calculate height
        temp_draw = ImageDraw.Draw(Image.new("RGB", (width, 10)))
        
        layout_data = []
        for section in sections:
            cat = section.get("category", "GENERAL").upper()
            content = section.get("content", "N/A")
            
            # Text wrapping logic
            wrapped_lines = self._wrap_text(content, self.font_main, width - (padding * 3))
            content_height = len(wrapped_lines) * 25
            
            layout_data.append({
                "cat": cat,
                "lines": wrapped_lines,
                "h": content_height + 40 # cat header + content
            })
            current_y += content_height + 40 + section_spacing

        total_height = current_y + 100
        
        # Create canvas
        img = Image.new("RGBA", (width, int(total_height)), COLOR_BG)
        draw = ImageDraw.Draw(img)

        # 1. Main LCARS 2.0 Frame (Rounded)
        frame_rect = [20, 20, width - 20, total_height - 20]
        self._draw_rounded_frame(draw, frame_rect, radius=50, width=5, color=COLOR_ACCENT)

        # 2. Header Block
        draw.text((padding + 20, 50), title, font=self.font_title, fill=COLOR_TEXT)
        draw.rectangle([padding, 95, width - padding, 100], fill=COLOR_ACCENT)

        # 3. Render Sections
        y = 130
        for item in layout_data:
            # Category Header (Subtle Bar)
            draw.rectangle([padding, y, padding + 150, y + 25], fill=COLOR_ACCENT)
            draw.text((padding + 10, y), item["cat"], font=self.font_cat, fill=COLOR_BG)
            
            y += 35
            # Content (Translucent Frame)
            frame_h = len(item["lines"]) * 25 + 20
            draw.rectangle([padding + 10, y, width - padding - 10, y + frame_h], fill=COLOR_FRAME)
            
            text_y = y + 10
            for line in item["lines"]:
                draw.text((padding + 30, text_y), line, font=self.font_main, fill=COLOR_TEXT)
                text_y += 25
            
            y += frame_h + section_spacing

        # Footer
        draw.text((width - 250, total_height - 60), "LCARS 2.0 SECURE PROTOCOL", font=self.font_main, fill=COLOR_ACCENT)

        # Save to BytesIO
        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=90)
        output.seek(0)
        return output

    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        lines = []
        # Simple character-based wrapping for multi-language support
        current_line = ""
        for char in text:
            test_line = current_line + char
            w = font.getbbox(test_line)[2]
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines

    def _draw_rounded_frame(self, draw, rect, radius, width, color):
        x1, y1, x2, y2 = rect
        # Draw the rounded corners
        draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=color, width=width)
        draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 0, fill=color, width=width)
        draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=color, width=width)
        draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=color, width=width)
        
        # Draw the straight bars
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=color, width=width)
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=color, width=width)
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=color, width=width)
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=color, width=width)

# Singleton instance
_instance = VisualCore()

def render_report(report_data: Dict[str, Any]) -> io.BytesIO:
    return _instance.render_report(report_data)

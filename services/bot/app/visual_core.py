import os
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Optional

# LCARS 2.0 (Picard) Color Palette
COLOR_BG = (12, 18, 36)          # Dark Navy Background
COLOR_TEXT = (255, 255, 255)      # White Text
COLOR_TITLE = (255, 180, 60)      # Warm Orange for Titles
COLOR_CATEGORY = (100, 200, 255)  # Cyan for Category Headers
COLOR_CONTENT = (220, 220, 220)   # Light Gray for Content

# Template types
TEMPLATE_STATUS = "status"
TEMPLATE_REPORT = "report"  
TEMPLATE_ALERT = "alert"

class VisualCore:
    def __init__(self):
        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        
        # Load template backgrounds
        self.templates = {}
        self._load_templates()
        
        # Font initialization
        self._init_fonts()
    
    def _load_templates(self):
        """Load LCARS 2.0 background templates."""
        templates = {
            TEMPLATE_STATUS: "lcars_status.png",
            TEMPLATE_REPORT: "lcars_report.png",
            TEMPLATE_ALERT: "lcars_alert.png"
        }
        for tpl_type, filename in templates.items():
            path = os.path.join(self.assets_dir, filename)
            if os.path.exists(path):
                self.templates[tpl_type] = Image.open(path).convert("RGBA")
            else:
                self.templates[tpl_type] = None
    
    def _init_fonts(self):
        """Initialize fonts with fallback."""
        font_paths = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "Arial.ttf"
        ]
        
        self.font_title = None
        self.font_category = None
        self.font_content = None
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    self.font_title = ImageFont.truetype(path, 28)
                    self.font_category = ImageFont.truetype(path, 22)
                    self.font_content = ImageFont.truetype(path, 18)
                    break
                except:
                    continue
        
        if not self.font_title:
            self.font_title = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_content = ImageFont.load_default()

    def render_report(self, report_data: Dict[str, Any], template_type: str = TEMPLATE_REPORT) -> io.BytesIO:
        """
        Renders a structured report using LCARS 2.0 templates.
        
        Args:
            report_data: Dict with 'title' and 'sections' list
            template_type: One of 'status', 'report', 'alert'
        """
        title = report_data.get("title", "LCARS REPORT").upper()
        sections = report_data.get("sections", [])
        
        # Get template background
        template = self.templates.get(template_type)
        
        if template:
            # Use pre-rendered template as background
            img = template.copy()
            width, height = img.size
        else:
            # Fallback to programmatic rendering
            width, height = 1024, 1024
            img = Image.new("RGBA", (width, height), COLOR_BG)
        
        draw = ImageDraw.Draw(img)
        
        # Define content zones based on template type
        if template_type == TEMPLATE_STATUS:
            # Status template: title at top, content in center/right panels
            title_zone = (180, 10, width - 20, 60)
            content_zones = [
                (180, 120, 380, 280),   # Left panel
                (400, 120, width - 20, 280),  # Top right
                (180, 300, 380, 460),   # Bottom left
                (400, 300, width - 20, 460),  # Bottom center/right
            ]
        elif template_type == TEMPLATE_ALERT:
            # Alert template: title prominent, single main content area
            title_zone = (200, 50, width - 100, 120)
            content_zones = [
                (200, 200, width - 100, height - 150),  # Main alert content
            ]
        else:
            # Report template: left sidebar, content on right
            title_zone = (160, 10, width - 20, 60)
            content_zones = [
                (160, 80, width - 20, 180),
                (160, 200, width - 20, 300),
                (160, 320, width - 20, 420),
                (160, 440, width - 20, 540),
            ]
        
        # Draw title
        tx, ty, tw, th = title_zone
        draw.text((tx + 10, ty + 5), title, font=self.font_title, fill=COLOR_TITLE)
        
        # Draw sections into content zones
        for i, section in enumerate(sections):
            if i >= len(content_zones):
                break  # No more zones available
            
            zone = content_zones[i]
            zx, zy, zw, zh = zone
            zone_width = zw - zx - 20
            zone_height = zh - zy - 10
            
            category = section.get("category", "").upper()
            content = section.get("content", "")
            
            # Draw category header
            if category:
                draw.text((zx + 10, zy + 5), category, font=self.font_category, fill=COLOR_CATEGORY)
                content_start_y = zy + 30
            else:
                content_start_y = zy + 10
            
            # Draw wrapped content
            wrapped = self._wrap_text(content, self.font_content, zone_width)
            line_y = content_start_y
            for line in wrapped:
                if line_y + 20 > zh:
                    break  # Exceeded zone height
                draw.text((zx + 10, line_y), line, font=self.font_content, fill=COLOR_CONTENT)
                line_y += 22
        
        # Convert to BytesIO for sending
        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=92)
        output.seek(0)
        return output

    def render_simple_status(self, status_text: str) -> io.BytesIO:
        """Renders a simple single-line status using the status template."""
        return self.render_report({
            "title": "SYSTEM STATUS",
            "sections": [{"category": "STATUS", "content": status_text}]
        }, template_type=TEMPLATE_STATUS)

    def render_alert(self, alert_title: str, alert_content: str) -> io.BytesIO:
        """Renders an alert/warning message."""
        return self.render_report({
            "title": alert_title.upper(),
            "sections": [{"category": "ALERT", "content": alert_content}]
        }, template_type=TEMPLATE_ALERT)

    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Wraps text to fit within max_width, supporting CJK characters."""
        if not text:
            return []
        
        lines = []
        current_line = ""
        
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
                
            test_line = current_line + char
            try:
                bbox = font.getbbox(test_line)
                w = bbox[2] - bbox[0]
            except:
                w = len(test_line) * 12  # Fallback width estimate
            
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return lines


# Singleton instance
_instance = VisualCore()

def render_report(report_data: Dict[str, Any], template_type: str = TEMPLATE_REPORT) -> io.BytesIO:
    """Public API for rendering reports."""
    return _instance.render_report(report_data, template_type)

def render_status(status_text: str) -> io.BytesIO:
    """Public API for simple status messages."""
    return _instance.render_simple_status(status_text)

def render_alert(title: str, content: str) -> io.BytesIO:
    """Public API for alert messages."""
    return _instance.render_alert(title, content)

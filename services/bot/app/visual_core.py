"""
LCARS 2.0 Visual Rendering Engine (Picard Season 3 / Titan-A Spec)
Strict implementation of 25th Century Starfleet UI visual grammar.
"""
import io
import random
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple

# ============================================================================
# COLOR PALETTE (Dave Blass / Michael Okuda - Season 3 Spec)
# ============================================================================
class LCARS2Colors:
    # Base
    BG_DEEP = (5, 7, 10)              # Deep Space Black
    GLASS_BG = (92, 153, 175, 25)     # 10% Opacity Steel Blue

    # Accents - Primary (Titan-A Style)
    TITAN_RED = (214, 60, 60)         # Command Red (New distinct shade)
    NEON_CYAN = (0, 242, 255)         # Primary System Lines
    STEEL_BLUE = (92, 153, 175)       # Framework / Passive
    
    # Accents - Functional
    ALERT_ORANGE = (255, 153, 0)      # Warnings
    GOLD = (255, 204, 102)            # Command / Highlight
    
    # Text
    TEXT_PRIMARY = (224, 250, 255)    # Ice White
    TEXT_DIM = (140, 180, 200)        # Dimmed Data
    TEXT_ALERT = (255, 80, 80)        # Red Text

# ============================================================================
# COMPONENT PRIMITIVES (The "Lego" Bricks)
# ============================================================================
class LCARS2Primitives:
    
    @staticmethod
    def draw_split_elbow(draw: ImageDraw, x: int, y: int, w: int, h: int, 
                         thickness: int, color: Tuple, corner: str = 'tl'):
        """
        Draws an LCARS 2.0 'Split Elbow' - The signature element.
        Unlike TNG, the horizontal and vertical bars are separated by a small gap
        or connected by a thin hairline, and often have a 'cap'.
        """
        gap = 4
        hairline_w = 2
        radius = int(thickness * 1.5)
        
        # We draw this by constructing specific shapes based on corner orientation
        # Simplified for code clarity: We draw a standard elbow but with the 'split' logic
        
        if corner == 'tl':
            # Vertical Segment (Left)
            # The vertical part is usually the dominant "thick" part
            draw.rectangle([x, y + radius, x + thickness, y + h], fill=color)
            
            # The joint arc
            draw.pieslice([x, y, x + radius*2, y + radius*2], 180, 270, fill=color)
            
            # The horizontal "Split" - A thin connector then the bar
            # In LCARS 2.0, sometimes the horizontal bar is thinner or detached.
            # We will perform the "Titan" style: Solid curve, but separated top bar.
            
            # Actually, looking at Titan-A, the classic "Elbow" is often just a solid sweep
            # BUT, the parallel line is what makes it 2.0.
            
            # Let's start with a solid base elbow for stability
            LCARS2Primitives.draw_solid_elbow(draw, x, y, w, h, thickness, color, corner)
            
            # Now add the signature "Parallel Rail"
            # A thin line following the inside curve
            rail_gap = 6
            rail_w = 2
            rx = x + thickness + rail_gap
            ry = y + thickness + rail_gap
            rw = w - thickness - rail_gap
            rh = h - thickness - rail_gap
            
            # Inner rail vertical
            draw.rectangle([rx, ry + radius, rx + rail_w, y + h], fill=LCARS2Colors.STEEL_BLUE)
            # Inner rail horizontal
            draw.rectangle([rx + radius, y + thickness + rail_gap, x + w, y + thickness + rail_gap + rail_w], fill=LCARS2Colors.STEEL_BLUE)
            # Inner rail arc
            # draw.arc([rx, ry, rx + radius*2, ry + radius*2], 180, 270, fill=LCARS2Colors.STEEL_BLUE, width=rail_w)
            
    @staticmethod
    def draw_solid_elbow(draw: ImageDraw, x: int, y: int, w: int, h: int, 
                        thickness: int, color: Tuple, corner: str = 'tl'):
        """Standard rounded elbow base."""
        r_out = thickness + 20 # fixed curve radius for consistency
        r_in = 20
        
        if corner == 'tl':
            # V-Bar
            draw.rectangle([x, y + r_out, x + thickness, y + h], fill=color)
            # H-Bar
            draw.rectangle([x + r_out, y, x + w, y + thickness], fill=color)
            # Corner
            draw.pieslice([x, y, x + r_out*2, y + r_out*2], 180, 270, fill=color)
            # Cutout inner (optional for pixel perf, but PIL handles overlap fine)
            # To make it a true curve, we fill the inner wedge with BG? 
            # No, PIL pieslice is solid. We need to draw the inner cutout if we want transparency.
            # For simplicity, we just draw the positive shapes.
            # Inner negative space correction (The "Inside Corner")
            draw.pieslice([x + thickness, y + thickness, x + thickness + r_in*2, y + thickness + r_in*2], 180, 270, fill=LCARS2Colors.BG_DEEP)
            draw.rectangle([x + thickness, y + thickness, x + w, y + h], fill=LCARS2Colors.BG_DEEP) # Clear inside

    @staticmethod
    def draw_bracket_frame(draw: ImageDraw, x: int, y: int, w: int, h: int, 
                          color: Tuple, thickness: int = 4):
        """
        Draws the standard '[ ]' or open bracket frame used for content panels.
        Titan-A style: Thin lines, rounded caps at ends.
        """
        cap_len = 30
        
        # Top Left Cap
        draw.rectangle([x, y, x + cap_len, y + thickness], fill=color) # Top bar
        draw.rectangle([x, y, x + thickness, y + cap_len], fill=color) # Side drop
        
        # Top Right Cap
        draw.rectangle([x + w - cap_len, y, x + w, y + thickness], fill=color)
        draw.rectangle([x + w - thickness, y, x + w, y + cap_len], fill=color)
        
        # Bottom Left Cap
        draw.rectangle([x, y + h - thickness, x + cap_len, y + h], fill=color)
        draw.rectangle([x, y + h - cap_len, x + thickness, y + h], fill=color)
        
        # Bottom Right Cap
        draw.rectangle([x + w - cap_len, y + h - thickness, x + w, y + h], fill=color)
        draw.rectangle([x + w - thickness, y + h - cap_len, x + w, y + h], fill=color)
        
        # Connectors (Optional, sometimes brackets are open)
        # We'll make them open for the "Airy" 2.0 look, or close them with thin lines
        
        # Thin connectors (1px)
        thin_color = (color[0], color[1], color[2], 128) # Semi-transparent
        draw.rectangle([x + cap_len, y, x + w - cap_len, y + 1], fill=thin_color) # Top hairline
        draw.rectangle([x + cap_len, y + h - 1, x + w - cap_len, y + h], fill=thin_color) # Bottom hairline

    @staticmethod
    def draw_glass_panel(img: Image, x: int, y: int, w: int, h: int):
        """
        Creates a semi-transparent glass backing for text areas.
        """
        # Create a new layer for the alpha composite
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([x, y, x + w, y + h], fill=LCARS2Colors.GLASS_BG)
        
        # Composite
        img.alpha_composite(overlay)

# ============================================================================
# LAYOUT ENGINE
# ============================================================================
class LCARS2Layout:
    def __init__(self):
        self._init_fonts()
        
    def _init_fonts(self):
        # We need rigorous font fallback
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Standard Linux
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc", # macOS
            "arialbd.ttf"
        ]
        
        self.font_header = None
        self.font_data = None
        self.font_tiny = None
        
        for p in font_paths:
            try:
                self.font_header = ImageFont.truetype(p, 36) # LCARS 2.0 Headers are BIG
                self.font_data = ImageFont.truetype(p, 18)
                self.font_tiny = ImageFont.truetype(p, 10) # For greebles
                break
            except:
                continue
                
        if not self.font_header:
            self.font_header = ImageFont.load_default()
            self.font_data = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()

# ============================================================================
# RENDERING FUNCTIONS
# ============================================================================
def render_personnel_file(profile_data: Dict[str, Any]) -> io.BytesIO:
    """
    Renders a High-Fidelity LCARS 2.0 Personnel File.
    """
    width = 800
    height = 450
    
    img = Image.new("RGBA", (width, height), LCARS2Colors.BG_DEEP)
    draw = ImageDraw.Draw(img)
    layout = LCARS2Layout()
    
    # 1. Base Framework (The "Titan" style bracket)
    margin = 20
    content_w = width - margin*2
    content_h = height - margin*2
    
    # Draw the main "Bracket Frame" around the content
    LCARS2Primitives.draw_bracket_frame(draw, margin, margin, content_w, content_h, LCARS2Colors.NEON_CYAN)
    
    # 2. Header Block
    header_h = 60
    # Top Left solid block for header
    draw.rectangle([margin, margin, margin + 400, margin + header_h], fill=LCARS2Colors.TITAN_RED)
    # Cutout for text
    title_text = "PERSONNEL RECORD"
    draw.text((margin + 20, margin + 10), title_text, font=layout.font_header, fill=LCARS2Colors.BG_DEEP)
    
    # 3. Glass Panel Background for Data
    panel_y = margin + header_h + 10
    panel_h = content_h - header_h - 10
    LCARS2Primitives.draw_glass_panel(img, margin, panel_y, content_w, panel_h)
    
    # 4. Data Population
    # Left Column: Portrait Placeholder & Key Stats
    col1_x = margin + 20
    col2_x = margin + 300
    
    # Simulated Photo Frame (No real photo yet, just wireframe)
    photo_w = 150
    photo_h = 180
    draw.rectangle([col1_x, panel_y + 20, col1_x + photo_w, panel_y + 20 + photo_h], outline=LCARS2Colors.STEEL_BLUE, width=1)
    # Placeholder cross
    draw.line([col1_x, panel_y + 20, col1_x + photo_w, panel_y + 20 + photo_h], fill=LCARS2Colors.STEEL_BLUE)
    draw.line([col1_x + photo_w, panel_y + 20, col1_x, panel_y + 20 + photo_h], fill=LCARS2Colors.STEEL_BLUE)
    
    # Data Rows
    current_y = panel_y + 20
    
    # Name (Big)
    name = profile_data.get("name", "Unknown").upper()
    draw.text((col2_x, current_y), name, font=layout.font_header, fill=LCARS2Colors.TEXT_PRIMARY)
    
    current_y += 50
    # Rank & Serial (Subtitle)
    rank = profile_data.get("rank", "Ensign").upper()
    user_id = profile_data.get("user_id", "Unknown")
    sub_text = f"{rank}  //  SERIAL: {user_id}"
    draw.text((col2_x, current_y), sub_text, font=layout.font_data, fill=LCARS2Colors.TEXT_DIM)
    
    current_y += 40
    # Divider Line
    draw.rectangle([col2_x, current_y, width - margin - 20, current_y + 2], fill=LCARS2Colors.ORANGE_BRIGHT if profile_data.get("is_core_officer") else LCARS2Colors.NEON_CYAN)
    
    current_y += 20
    # Detailed Stats (Grid)
    stats = [
        ("ASSIGNMENT", profile_data.get("station", "General Duty")),
        ("DEPARTMENT", profile_data.get("department", "Operations")),
        ("CLEARANCE", f"LEVEL {profile_data.get('clearance', 1)}"),
        ("STATUS", "ACTIVE DUTY" if not profile_data.get("restricted") else "RESTRICTED")
    ]
    
    for label, value in stats:
        draw.text((col2_x, current_y), label, font=layout.font_tiny, fill=LCARS2Colors.NEON_CYAN)
        draw.text((col2_x + 120, current_y), str(value).upper(), font=layout.font_data, fill=LCARS2Colors.TEXT_PRIMARY)
        current_y += 30

    # 5. Greebles (The 2.0 Flavor)
    # Random numbers in corners
    draw.text((margin + 5, height - margin - 15), f"LCARS {random.randint(400,900)}", font=layout.font_tiny, fill=LCARS2Colors.TEXT_DIM)
    draw.text((width - margin - 50, margin + 5), "SEC-01", font=layout.font_tiny, fill=LCARS2Colors.TEXT_DIM)

    # Convert to bytes
    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=95)
    output.seek(0)
    return output

# Public API Wrappers
def render_status(status_text: str) -> io.BytesIO:
    return render_personnel_file({"name": "SYSTEM STATUS", "rank": status_text, "station": "N/A"})

def render_report(report_data: Dict, template_type: str = "default") -> io.BytesIO:
    return render_personnel_file({"name": report_data.get("title"), "rank": "REPORT", "station": str(len(report_data.get("sections", []))) + " SECTIONS"})

def render_alert(title: str, content: str) -> io.BytesIO:
    return render_personnel_file({"name": title, "rank": "ALERT", "station": content})

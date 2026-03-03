"""
FocusBeast Image Engine — Professional Design System
Clean typography, geometric pet art, no emojis in images.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io, math, random
from dataclasses import dataclass
from typing import Tuple, Optional

# ── Font paths ─────────────────────────────────────────────────────────────────
_FB = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
_FM = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
_FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
_FL = "/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf"

def _f(size, bold=False, medium=False, light=False):
    p = _FB if bold else _FM if medium else _FL if light else _FR
    try:    return ImageFont.truetype(p, size)
    except: return ImageFont.load_default()

def _cx(draw, text, font, container_w, offset_x=0):
    bb = draw.textbbox((0,0), text, font=font)
    return offset_x + (container_w - (bb[2]-bb[0])) // 2

def _lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def _to_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf

# ── Themes ─────────────────────────────────────────────────────────────────────
@dataclass
class Theme:
    name: str
    discord_color: int
    bg_top: Tuple[int,int,int]
    bg_bot: Tuple[int,int,int]
    accent: Tuple[int,int,int]       # progress bar, highlights
    accent2: Tuple[int,int,int]      # secondary accent
    text_primary: Tuple[int,int,int]
    text_secondary: Tuple[int,int,int]
    panel_bg: Tuple[int,int,int]
    bar_track: Tuple[int,int,int]
    label: str                        # short uppercase label shown top-left

THEMES = {
    "study": Theme(
        "study", 0x0D1B4B,
        (7, 17, 55),   (4, 10, 35),
        (255,255,255), (100,140,255),
        (255,255,255), (120,150,220),
        (14, 26, 75),  (20, 35, 90),
        "FOCUS MODE",
    ),
    "midnight": Theme(
        "midnight", 0x08080F,
        (8, 8, 14),    (4, 4, 10),
        (160,100,255), (100,60,200),
        (240,230,255), (140,120,200),
        (14, 14, 22),  (20, 20, 30),
        "MIDNIGHT GRIND",
    ),
    "lofi": Theme(
        "lofi", 0x2A1A3E,
        (22, 14, 38),  (14, 8, 26),
        (200,140,255), (140,80,220),
        (235,215,255), (160,130,200),
        (30, 18, 50),  (40, 24, 64),
        "LOFI BEATS",
    ),
    "nature": Theme(
        "nature", 0x0A2010,
        (10, 26, 14),  (6, 16, 8),
        (80, 200,100), (40,160, 60),
        (210,255,220), (130,200,140),
        (14, 36, 18),  (18, 48, 22),
        "DEEP FOCUS",
    ),
    "space": Theme(
        "space", 0x04041A,
        (4,  4,  22),  (2,  2,  14),
        (80,120,255),  (40, 80,200),
        (210,220,255), (130,150,230),
        (8,  8,  36),  (12, 12, 48),
        "SPACE MODE",
    ),
    "ocean": Theme(
        "ocean", 0x031428,
        (4, 18, 42),   (2, 10, 26),
        (40,190,255),  (0,140,220),
        (200,240,255), (100,200,240),
        (6, 26, 58),   (8, 34, 72),
        "FLOW STATE",
    ),
    "fire": Theme(
        "fire", 0x280400,
        (32, 8,  2),   (18, 4,  1),
        (255, 80, 10), (200,50,  0),
        (255,220,170), (220,150, 80),
        (44, 12, 4),   (56, 16, 6),
        "GRIND MODE",
    ),
    "sakura": Theme(
        "sakura", 0x300A1A,
        (38, 12, 24),  (24, 6, 16),
        (255,150,185), (210,100,145),
        (255,230,240), (220,170,195),
        (50, 16, 32),  (64, 20, 42),
        "BLOOM SESSION",
    ),
    "cyberpunk": Theme(
        "cyberpunk", 0x08001A,
        (8,  2, 22),   (4,  1, 14),
        (0, 240,200),  (0,180,160),
        (220,200,255), (160,140,220),
        (12, 4, 32),   (16, 6, 42),
        "CYBER LOCK",
    ),
    "golden": Theme(
        "golden", 0x1A1000,
        (22, 14, 2),   (14, 8,  1),
        (220,175, 30), (170,130, 15),
        (255,245,200), (220,195,120),
        (30, 20, 4),   (40, 26, 6),
        "CHAMPION MODE",
    ),
}

# ── Motivational Quotes ────────────────────────────────────────────────────────
QUOTES = [
    "The secret of getting ahead is getting started.",
    "Discipline is choosing what you want most over what you want now.",
    "You don't have to be great to start. You have to start to be great.",
    "Focus is the art of knowing what to ignore.",
    "Success is the sum of small efforts, repeated every day.",
    "The harder you work, the luckier you get.",
    "Don't watch the clock. Do what it does. Keep going.",
    "Great things never come from comfort zones.",
    "Your future self is watching you right now through memories.",
    "It always seems impossible until it is done.",
    "The pain of discipline is less than the pain of regret.",
    "Every expert was once a beginner. Keep going.",
    "Consistency beats motivation. Show up anyway.",
    "The grind is the goal.",
    "One focused hour beats ten distracted ones.",
    "Champions train. Everyone else makes excuses.",
    "Today's effort is tomorrow's advantage.",
    "You are one session away from a breakthrough.",
    "Quiet the noise. Lock in.",
    "The world rewards those who do the work.",
    "Nobody regrets a great study session.",
    "Make now count.",
    "Work in silence. Let results speak.",
    "Your mind is a weapon. Keep it sharp.",
    "Push through. The other side is worth it.",
]

def _quote(remaining: int, total: int) -> str:
    slot = (total - remaining) // 180
    return QUOTES[slot % len(QUOTES)]

# ── Rarity meta ────────────────────────────────────────────────────────────────
RARITY_COLORS = {
    "common":    (160, 160, 160),
    "uncommon":  (60,  200,  80),
    "rare":      (80,  140, 255),
    "legendary": (255, 170,  20),
}
RARITY_LABELS = {
    "common":    "COMMON",
    "uncommon":  "UNCOMMON",
    "rare":      "RARE",
    "legendary": "LEGENDARY",
}

# ── Pet definitions ────────────────────────────────────────────────────────────
PIXEL_PETS = {
    "bunny":      {"rarity": "common",    "price": 150,  "desc": "Soft and swift. Hops during your grind."},
    "fox":        {"rarity": "common",    "price": 200,  "desc": "Clever and quick. Never misses a session."},
    "cat":        {"rarity": "common",    "price": 200,  "desc": "Mysterious and calm. Purrs during your grind."},
    "wolf":       {"rarity": "uncommon",  "price": 500,  "desc": "Loyal guardian. Howls at the moon for you."},
    "owl":        {"rarity": "uncommon",  "price": 500,  "desc": "Wise companion. Boosts your focus aura."},
    "penguin":    {"rarity": "uncommon",  "price": 450,  "desc": "Chill vibes. Keeps you cool under pressure."},
    "dragon":     {"rarity": "rare",      "price": 1500, "desc": "Ancient power. XP gains are doubled."},
    "unicorn":    {"rarity": "rare",      "price": 1500, "desc": "Magical focus. Every session sparkles."},
    "phoenix":    {"rarity": "legendary", "price": 5000, "desc": "Reborn from focus. The ultimate companion."},
    "galaxy_cat": {"rarity": "legendary", "price": 5000, "desc": "Cosmic entity. Exists across all dimensions."},
}


# ═══════════════════════════════════════════════════════════════════════════════
# PET ART RENDERER — Geometric / vector-style clean animal illustrations
# No emojis. Each pet drawn with shapes, curves, and Pillow primitives.
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_pet(draw: ImageDraw.ImageDraw, species: str, cx: int, cy: int, size: int):
    """Draw a clean geometric pet illustration centered at (cx,cy) with given size."""
    s = size / 100  # scale factor — design is in 100-unit space

    def pt(x, y):   return (int(cx + x*s), int(cy + y*s))
    def r(x,y,w,h): return [cx+int(x*s), cy+int(y*s), cx+int((x+w)*s), cy+int((y+h)*s)]
    def el(x,y,rx,ry): return [cx+int((x-rx)*s), cy+int((y-ry)*s), cx+int((x+rx)*s), cy+int((y+ry)*s)]

    if   species == "bunny":    _pet_bunny(draw,    pt,r,el,s,cx,cy)
    elif species == "fox":      _pet_fox(draw,      pt,r,el,s,cx,cy)
    elif species == "cat":      _pet_cat(draw,      pt,r,el,s,cx,cy)
    elif species == "wolf":     _pet_wolf(draw,     pt,r,el,s,cx,cy)
    elif species == "owl":      _pet_owl(draw,      pt,r,el,s,cx,cy)
    elif species == "penguin":  _pet_penguin(draw,  pt,r,el,s,cx,cy)
    elif species == "dragon":   _pet_dragon(draw,   pt,r,el,s,cx,cy)
    elif species == "unicorn":  _pet_unicorn(draw,  pt,r,el,s,cx,cy)
    elif species == "phoenix":  _pet_phoenix(draw,  pt,r,el,s,cx,cy)
    elif species == "galaxy_cat": _pet_galaxy_cat(draw, pt,r,el,s,cx,cy)
    else: _pet_cat(draw, pt,r,el,s,cx,cy)


def _pet_bunny(draw, pt, r, el, s, cx, cy):
    # Lop-eared brown bunny
    C = {"body":(190,130,65),"dark":(130,85,38),"outline":(80,45,18),"eye":(20,12,5),"nose":(220,150,160),"belly":(230,200,160),"ear_in":(230,160,170)}
    # Left drooping ear
    draw.ellipse(el(-28,-55,10,30), fill=C["dark"], outline=C["outline"], width=int(2*s))
    draw.ellipse(el(-28,-55,6,24),  fill=C["ear_in"])
    # Right ear (behind head)
    draw.ellipse(el(22,-50,9,26),   fill=C["dark"], outline=C["outline"], width=int(2*s))
    # Body
    draw.ellipse(el(0,28,42,38),    fill=C["body"], outline=C["outline"], width=int(2*s))
    # Belly
    draw.ellipse(el(0,32,26,26),    fill=C["belly"])
    # Head
    draw.ellipse(el(0,-14,34,30),   fill=C["body"], outline=C["outline"], width=int(2*s))
    # Eye
    draw.ellipse(el(-12,-18,7,7),   fill=C["eye"])
    draw.ellipse(el(-10,-20,2,2),   fill=(255,255,255))
    # Nose
    draw.ellipse(el(-2,-4,4,3),     fill=C["nose"])
    # Whisker lines
    for ox,oy in [(-18,-2),(-22,0),(-18,2)]:
        draw.line([pt(ox,oy),pt(-6,oy)], fill=C["dark"], width=max(1,int(1.5*s)))
    # Small tail
    draw.ellipse(el(36,22,8,8),     fill=C["belly"], outline=C["outline"], width=int(1.5*s))
    # Feet
    draw.ellipse(el(-20,58,18,10),  fill=C["body"], outline=C["outline"], width=int(2*s))
    draw.ellipse(el(16,58,18,10),   fill=C["body"], outline=C["outline"], width=int(2*s))

def _pet_fox(draw, pt, r, el, s, cx, cy):
    C = {"body":(220,110,30),"light":(245,165,70),"white":(240,220,195),"dark":(140,60,10),"outline":(100,40,5),"eye":(30,15,5),"nose":(50,25,15)}
    # Tail — big fluffy behind
    draw.ellipse(el(40,30,28,42),   fill=C["body"],  outline=C["outline"], width=int(2*s))
    draw.ellipse(el(52,28,16,16),   fill=(240,240,240))
    # Body
    draw.ellipse(el(0,28,40,36),    fill=C["body"],  outline=C["outline"], width=int(2*s))
    # Belly
    draw.ellipse(el(0,32,24,24),    fill=C["white"])
    # Left ear (pointy)
    draw.polygon([pt(-22,-54), pt(-38,-28), pt(-8,-28)], fill=C["body"],  outline=C["outline"])
    draw.polygon([pt(-22,-50), pt(-32,-32), pt(-12,-32)],fill=C["light"])
    # Right ear
    draw.polygon([pt(22,-54),  pt(8,-28),  pt(38,-28)],  fill=C["body"],  outline=C["outline"])
    draw.polygon([pt(22,-50),  pt(12,-32), pt(32,-32)],   fill=C["light"])
    # Head
    draw.ellipse(el(0,-16,33,28),   fill=C["body"],  outline=C["outline"], width=int(2*s))
    # White muzzle
    draw.ellipse(el(0,-4,16,14),    fill=C["white"])
    # Eyes
    for ex in [-14, 14]:
        draw.ellipse(el(ex,-22,6,6),  fill=C["eye"])
        draw.ellipse(el(ex-1,-24,2,2),fill=(255,255,255))
    # Nose
    draw.ellipse(el(0,2,5,4),       fill=C["nose"])
    # Legs
    for lx in [-18, 14]:
        draw.ellipse(el(lx,60,12,10), fill=C["body"], outline=C["outline"], width=int(2*s))

def _pet_cat(draw, pt, r, el, s, cx, cy):
    C = {"body":(165,148,175),"light":(200,185,212),"dark":(90,75,105),"outline":(55,42,68),"eye":(50,160,200),"pupil":(15,10,20),"nose":(220,120,150),"stripe":(130,115,145)}
    # Body
    draw.ellipse(el(0,28,40,36),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Belly
    draw.ellipse(el(0,30,26,26),    fill=C["light"])
    # Pointy ears
    draw.polygon([pt(-22,-52), pt(-36,-24), pt(-8,-24)], fill=C["body"],   outline=C["outline"])
    draw.polygon([pt(-22,-46), pt(-30,-28), pt(-14,-28)],fill=C["light"])
    draw.polygon([pt(22,-52),  pt(8,-24),   pt(36,-24)], fill=C["body"],   outline=C["outline"])
    draw.polygon([pt(22,-46),  pt(14,-28),  pt(30,-28)], fill=C["light"])
    # Head
    draw.ellipse(el(0,-14,33,28),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Stripes on forehead
    for fy in [-28,-22,-16]:
        draw.line([pt(-8,fy), pt(8,fy)], fill=C["stripe"], width=max(1,int(2*s)))
    # Eyes  
    for ex in [-13, 13]:
        draw.ellipse(el(ex,-19,8,7),  fill=C["eye"])
        draw.ellipse(el(ex,-19,3,5),  fill=C["pupil"])
        draw.ellipse(el(ex-4,-22,2,2),fill=(255,255,255))
    # Nose
    draw.polygon([pt(0,-4),pt(-4,1),pt(4,1)], fill=C["nose"])
    # Mouth
    draw.line([pt(0,2),pt(-5,6)], fill=C["dark"], width=max(1,int(1.5*s)))
    draw.line([pt(0,2),pt(5,6)],  fill=C["dark"], width=max(1,int(1.5*s)))
    # Whiskers
    for oy in [-2, 2]:
        draw.line([pt(-8,oy),pt(-24,oy-2)], fill=C["dark"], width=max(1,int(1.2*s)))
        draw.line([pt(8,oy), pt(24,oy-2)],  fill=C["dark"], width=max(1,int(1.2*s)))
    # Tail
    draw.arc([cx+int(28*s), cy+int(10*s), cx+int(62*s), cy+int(60*s)], 200, 360, fill=C["body"], width=int(10*s))
    # Feet
    for lx in [-18, 14]:
        draw.ellipse(el(lx,60,14,9), fill=C["body"], outline=C["outline"], width=int(2*s))

def _pet_wolf(draw, pt, r, el, s, cx, cy):
    C = {"body":(120,125,145),"light":(170,175,195),"dark":(60,65,80),"outline":(38,42,55),"eye":(60,120,210),"pupil":(10,10,15),"nose":(40,40,50),"belly":(220,220,230)}
    # Body
    draw.ellipse(el(0,30,42,36),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Belly
    draw.ellipse(el(0,34,26,26),    fill=C["belly"])
    # Pointy ears
    draw.polygon([pt(-20,-54), pt(-36,-20), pt(-4,-20)],  fill=C["body"],   outline=C["outline"])
    draw.polygon([pt(-20,-48), pt(-30,-24), pt(-10,-24)], fill=C["light"])
    draw.polygon([pt(20,-54),  pt(4,-20),   pt(36,-20)],  fill=C["body"],   outline=C["outline"])
    draw.polygon([pt(20,-48),  pt(10,-24),  pt(30,-24)],  fill=C["light"])
    # Head
    draw.ellipse(el(0,-14,34,29),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Snout
    draw.ellipse(el(0,-2,18,13),    fill=C["light"])
    # Eyes
    for ex in [-14, 14]:
        draw.ellipse(el(ex,-22,7,7),  fill=C["eye"])
        draw.ellipse(el(ex,-22,3,4),  fill=C["pupil"])
        draw.ellipse(el(ex-2,-24,2,2),fill=(255,255,255))
    # Nose
    draw.ellipse(el(0,2,6,4),       fill=C["nose"])
    # Legs
    for lx in [-18, 12]:
        draw.ellipse(el(lx,62,14,9), fill=C["body"], outline=C["outline"], width=int(2*s))
    # Tail
    draw.arc([cx+int(30*s), cy-int(10*s), cx+int(68*s), cy+int(52*s)], 190, 360, fill=C["body"], width=int(12*s))

def _pet_owl(draw, pt, r, el, s, cx, cy):
    C = {"body":(145,108,55),"light":(195,158,90),"dark":(90,62,25),"outline":(60,38,12),"eye_ring":(240,200,60),"eye":(20,15,5),"beak":(210,155,50),"belly":(220,200,160),"wing":(110,80,35)}
    # Body (round)
    draw.ellipse(el(0,14,46,50),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Belly pattern
    draw.ellipse(el(0,18,30,36),    fill=C["belly"])
    # Wing left
    draw.ellipse(el(-38,20,18,34),  fill=C["wing"],   outline=C["outline"], width=int(2*s))
    # Wing right
    draw.ellipse(el(38,20,18,34),   fill=C["wing"],   outline=C["outline"], width=int(2*s))
    # Head
    draw.ellipse(el(0,-22,36,32),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Ear tufts
    draw.polygon([pt(-18,-50), pt(-30,-26), pt(-6,-26)],  fill=C["body"],  outline=C["outline"])
    draw.polygon([pt(18,-50),  pt(6,-26),   pt(30,-26)],  fill=C["body"],  outline=C["outline"])
    # Big eye rings
    draw.ellipse(el(-14,-22,14,14), fill=C["eye_ring"])
    draw.ellipse(el(14,-22,14,14),  fill=C["eye_ring"])
    # Eyes
    draw.ellipse(el(-14,-22,10,10), fill=C["eye"])
    draw.ellipse(el(14,-22,10,10),  fill=C["eye"])
    draw.ellipse(el(-16,-24,3,3),   fill=(255,255,255))
    draw.ellipse(el(12,-24,3,3),    fill=(255,255,255))
    # Beak
    draw.polygon([pt(-5,-6),pt(5,-6),pt(0,4)], fill=C["beak"])
    # Feet
    for fx, fdir in [(-14,1),(14,-1)]:
        for toe in range(3):
            draw.line([pt(fx,62), pt(fx+fdir*(toe-1)*8, 72)], fill=C["dark"], width=int(3*s))

def _pet_penguin(draw, pt, r, el, s, cx, cy):
    C = {"body":(20,20,30),"belly":(240,240,245),"beak":(255,190,50),"feet":(255,160,40),"eye":(255,255,255),"pupil":(10,10,20),"wing":(15,15,25),"shine":(50,50,80)}
    # Body
    draw.ellipse(el(0,18,38,52),    fill=C["body"],   outline=C["shine"], width=int(2*s))
    # White belly
    draw.ellipse(el(0,16,24,40),    fill=C["belly"])
    # Head
    draw.ellipse(el(0,-26,30,28),   fill=C["body"],   outline=C["shine"], width=int(2*s))
    # Wings
    draw.ellipse(el(-44,18,16,34),  fill=C["wing"],   outline=C["shine"], width=int(1.5*s))
    draw.ellipse(el(44,18,16,34),   fill=C["wing"],   outline=C["shine"], width=int(1.5*s))
    # Eyes
    draw.ellipse(el(-10,-30,8,8),   fill=C["eye"])
    draw.ellipse(el(10,-30,8,8),    fill=C["eye"])
    draw.ellipse(el(-10,-30,4,4),   fill=C["pupil"])
    draw.ellipse(el(10,-30,4,4),    fill=C["pupil"])
    draw.ellipse(el(-12,-32,2,2),   fill=(200,200,255))
    draw.ellipse(el(8,-32,2,2),     fill=(200,200,255))
    # Beak
    draw.polygon([pt(-6,-16),pt(6,-16),pt(0,-8)], fill=C["beak"])
    # Feet
    draw.ellipse(el(-14,68,14,8),   fill=C["feet"])
    draw.ellipse(el(14,68,14,8),    fill=C["feet"])

def _pet_dragon(draw, pt, r, el, s, cx, cy):
    C = {"body":(35,160,60),"dark":(18,100,35),"light":(80,220,100),"belly":(160,235,170),"outline":(12,70,22),"eye":(255,215,40),"pupil":(10,15,10),"horn":(200,230,80),"wing":(25,130,50),"fire":(255,100,20)}
    # Wing left
    wing_pts_l = [pt(-40,-10),pt(-75,-50),pt(-60,10),pt(-30,30)]
    draw.polygon(wing_pts_l, fill=C["wing"], outline=C["outline"])
    # Wing right
    wing_pts_r = [pt(40,-10),pt(75,-50),pt(60,10),pt(30,30)]
    draw.polygon(wing_pts_r, fill=C["wing"], outline=C["outline"])
    # Body
    draw.ellipse(el(0,28,40,36),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    draw.ellipse(el(0,30,26,24),    fill=C["belly"])
    # Tail
    draw.arc([cx+int(28*s), cy+int(15*s), cx+int(72*s), cy+int(65*s)], 190, 355, fill=C["body"], width=int(14*s))
    draw.ellipse(el(58,48,8,8),     fill=C["light"])
    # Neck / head
    draw.ellipse(el(0,-20,28,34),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Horns
    draw.polygon([pt(-10,-50),pt(-18,-28),pt(-4,-28)], fill=C["horn"], outline=C["outline"])
    draw.polygon([pt(10,-50), pt(4,-28), pt(18,-28)],  fill=C["horn"], outline=C["outline"])
    # Snout
    draw.ellipse(el(0,-8,16,10),    fill=C["light"])
    # Nostrils / fire
    draw.ellipse(el(-5,-6,3,2),     fill=C["fire"])
    draw.ellipse(el(5,-6,3,2),      fill=C["fire"])
    # Eyes
    for ex in [-12,12]:
        draw.ellipse(el(ex,-26,8,8),  fill=C["eye"])
        draw.ellipse(el(ex,-26,3,5),  fill=C["pupil"])
        draw.ellipse(el(ex-2,-28,2,2),fill=(255,255,220))
    # Claws
    for lx in [-18, 14]:
        draw.ellipse(el(lx,60,14,9), fill=C["dark"], outline=C["outline"], width=int(2*s))
        for toe in range(3):
            draw.line([pt(lx-10+toe*10,66), pt(lx-12+toe*10,74)], fill=C["dark"], width=int(2.5*s))

def _pet_unicorn(draw, pt, r, el, s, cx, cy):
    C = {"body":(230,185,255),"light":(250,225,255),"dark":(160,100,210),"outline":(120,60,175),"eye":(20,12,30),"mane1":(255,160,210),"mane2":(180,120,255),"mane3":(120,200,255),"horn":(255,215,50),"hoof":(140,80,200)}
    # Body (horse-ish)
    draw.ellipse(el(0,24,46,40),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Neck
    draw.ellipse(el(-12,-4,20,28),  fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Mane flowing
    for i,(mx,my,mr,col) in enumerate([(-20,-30,14,C["mane1"]),(-24,-18,12,C["mane2"]),(-22,-6,10,C["mane3"]),(-20,6,9,C["mane1"])]):
        draw.ellipse(el(mx,my,mr,mr), fill=col)
    # Head
    draw.ellipse(el(0,-24,26,24),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Horn
    draw.polygon([pt(0,-56),pt(-6,-28),pt(6,-28)], fill=C["horn"], outline=(200,160,20))
    # Horn shimmer
    draw.line([pt(-1,-52),pt(-4,-36)], fill=(255,245,180), width=int(1.5*s))
    # Eye
    draw.ellipse(el(-10,-28,7,7),   fill=C["eye"])
    draw.ellipse(el(-12,-30,2,2),   fill=(255,255,255))
    # Nostril
    draw.ellipse(el(-4,-10,4,3),    fill=C["dark"])
    # Legs
    for lx,ly in [(-20,50),(-8,52),(8,52),(20,50)]:
        draw.rounded_rectangle([cx+int((lx-6)*s),cy+int(ly*s),cx+int((lx+6)*s),cy+int((ly+22)*s)], radius=int(5*s), fill=C["body"], outline=C["outline"])
        draw.rounded_rectangle([cx+int((lx-6)*s),cy+int((ly+16)*s),cx+int((lx+6)*s),cy+int((ly+24)*s)], radius=int(3*s), fill=C["hoof"])
    # Tail
    for i,(tx,ty,col) in enumerate([(52,20,C["mane1"]),(58,32,C["mane2"]),(56,44,C["mane3"])]):
        draw.ellipse(el(tx,ty,10,14), fill=col)

def _pet_phoenix(draw, pt, r, el, s, cx, cy):
    C = {"body":(220,80,15),"light":(255,160,40),"bright":(255,230,80),"dark":(160,30,5),"outline":(120,20,5),"eye":(255,230,60),"pupil":(30,10,5),"beak":(240,170,40),"feather1":(255,80,10),"feather2":(255,160,20),"feather3":(255,220,60)}
    # Tail feathers — dramatic spread
    tail_feathers = [
        ((-50,55),(-30,20),(- 10,60), C["feather1"]),
        ((-30,62),(-10,22),( 10,65), C["feather2"]),
        ((-10,65),( 10,20),( 30,62), C["feather2"]),
        (( 10,60),( 30,20),( 50,55), C["feather3"]),
        (( 30,55),( 50,15),( 65,50), C["feather1"]),
        ((-65,50),(-50,15),(-30,55), C["feather1"]),
    ]
    for p1,p2,p3,col in tail_feathers:
        draw.polygon([pt(*p1),pt(*p2),pt(*p3)], fill=col)
    # Wing left
    wing_l = [pt(-10,0),pt(-70,-30),pt(-80,20),pt(-55,50),pt(-20,40)]
    draw.polygon(wing_l, fill=C["body"], outline=C["dark"])
    wing_l_light = [pt(-15,5),pt(-62,-22),pt(-68,18),pt(-48,40),pt(-22,34)]
    draw.polygon(wing_l_light, fill=C["light"])
    # Wing right
    wing_r = [pt(10,0),pt(70,-30),pt(80,20),pt(55,50),pt(20,40)]
    draw.polygon(wing_r, fill=C["body"], outline=C["dark"])
    wing_r_light = [pt(15,5),pt(62,-22),pt(68,18),pt(48,40),pt(22,34)]
    draw.polygon(wing_r_light, fill=C["light"])
    # Body
    draw.ellipse(el(0,22,28,32),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    draw.ellipse(el(0,24,18,22),    fill=C["light"])
    # Neck
    draw.ellipse(el(-4,-8,18,22),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Head crest feathers
    for cx2,cy2,col in [(-8,-54,C["feather3"]),(0,-58,C["feather2"]),(8,-54,C["feather3"]),(14,-50,C["feather1"]),(-14,-50,C["feather1"])]:
        draw.polygon([pt(cx2,cy2),pt(cx2-5,-38),pt(cx2+5,-38)], fill=col)
    # Head
    draw.ellipse(el(0,-26,22,22),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Eye
    draw.ellipse(el(-8,-30,8,8),    fill=C["eye"])
    draw.ellipse(el(-8,-30,4,4),    fill=C["pupil"])
    draw.ellipse(el(-10,-32,2,2),   fill=(255,255,220))
    # Beak
    draw.polygon([pt(4,-26),pt(18,-22),pt(6,-18)], fill=C["beak"], outline=C["dark"])

def _pet_galaxy_cat(draw, pt, r, el, s, cx, cy):
    C = {"body":(80,40,160),"light":(130,70,220),"dark":(40,18,90),"outline":(25,10,60),"eye":(80,210,255),"pupil":(10,8,25),"nose":(200,80,255),"stripe":(100,50,190),"star":(255,220,80),"belly":(110,60,200)}
    # Body
    draw.ellipse(el(0,28,40,36),    fill=C["body"],   outline=C["outline"], width=int(2*s))
    draw.ellipse(el(0,30,26,26),    fill=C["belly"])
    # Star markings on belly
    for sx2,sy2 in [(-8,26),(4,34),(-4,42)]:
        draw.polygon([pt(sx2,sy2),pt(sx2-3,sy2+5),pt(sx2+3,sy2+5)], fill=C["star"])
    # Pointy ears with inner glow
    draw.polygon([pt(-22,-52), pt(-36,-22), pt(-8,-22)], fill=C["body"],  outline=C["outline"])
    draw.polygon([pt(-22,-46), pt(-30,-28), pt(-14,-28)],fill=C["light"])
    draw.polygon([pt(22,-52),  pt(8,-22),   pt(36,-22)], fill=C["body"],  outline=C["outline"])
    draw.polygon([pt(22,-46),  pt(14,-28),  pt(30,-28)], fill=C["light"])
    # Head
    draw.ellipse(el(0,-14,33,28),   fill=C["body"],   outline=C["outline"], width=int(2*s))
    # Cosmic stripes on forehead
    for fy in [-26,-20,-14]:
        draw.line([pt(-10,fy),pt(10,fy)], fill=C["stripe"], width=max(1,int(2*s)))
    # Glowing eyes
    draw.ellipse(el(-12,-20,10,9),  fill=C["eye"])
    draw.ellipse(el(12,-20,10,9),   fill=C["eye"])
    draw.ellipse(el(-12,-20,4,6),   fill=C["pupil"])
    draw.ellipse(el(12,-20,4,6),    fill=C["pupil"])
    draw.ellipse(el(-14,-22,3,3),   fill=(200,240,255))
    draw.ellipse(el(10,-22,3,3),    fill=(200,240,255))
    # Nose
    draw.polygon([pt(0,-4),pt(-4,1),pt(4,1)], fill=C["nose"])
    # Whiskers
    for oy in [-1,3]:
        draw.line([pt(-8,oy),pt(-26,oy-2)], fill=C["dark"], width=max(1,int(1.5*s)))
        draw.line([pt(8,oy), pt(26,oy-2)],  fill=C["dark"], width=max(1,int(1.5*s)))
    # Galaxy tail
    draw.arc([cx+int(28*s), cy+int(8*s), cx+int(66*s), cy+int(58*s)], 195, 360, fill=C["light"], width=int(12*s))
    # Star on tail tip
    draw.ellipse(el(54,40,6,6),     fill=C["star"])
    # Feet
    for lx in [-18, 14]:
        draw.ellipse(el(lx,60,14,9), fill=C["body"], outline=C["outline"], width=int(2*s))


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ImageEngine:

    # ── Timer Frame ────────────────────────────────────────────────────────────
    def render_timer(self, theme_name: str, remaining: int, total: int,
                     break_time: int, pet_key: str = None, pet_name: str = None) -> io.BytesIO:
        theme = THEMES.get(theme_name, THEMES["study"])
        W, H  = 1200, 675

        img  = Image.new("RGB", (W, H), theme.bg_top)
        draw = ImageDraw.Draw(img)

        # ── Background gradient ───────────────────────────────────────────────
        for y in range(H):
            draw.line([(0,y),(W,y)], fill=_lerp(theme.bg_top, theme.bg_bot, y/H))

        # ── Subtle dot grid ───────────────────────────────────────────────────
        dot_col = _lerp(theme.bg_top, theme.panel_bg, 1.5)
        for gx in range(0, W, 60):
            for gy in range(0, H, 60):
                draw.ellipse([gx-1, gy-1, gx+1, gy+1], fill=dot_col)

        # ── Top accent bar ────────────────────────────────────────────────────
        draw.rectangle([0, 0, W, 4], fill=theme.accent)

        # ── Theme label — top left ────────────────────────────────────────────
        draw.text((44, 28), theme.label,
                  font=_f(13, medium=True), fill=theme.accent)

        # ── Session stats — top right ─────────────────────────────────────────
        pct = int((1 - remaining/max(total,1)) * 100)
        draw.text((W-200, 28), f"{pct}% COMPLETE",
                  font=_f(13, medium=True), fill=theme.text_secondary)

        # ── Giant countdown — centered ────────────────────────────────────────
        mins, secs = remaining // 60, remaining % 60
        timer_str  = f"{mins:02d}:{secs:02d}"
        tf         = _f(200, bold=True)
        tx         = _cx(draw, timer_str, tf, W)
        # Soft shadow
        draw.text((tx+4, 109), timer_str, font=tf, fill=_lerp(theme.bg_bot,(0,0,0),0.4))
        # Main text
        draw.text((tx,   105), timer_str, font=tf, fill=theme.text_primary)

        # ── Progress bar ──────────────────────────────────────────────────────
        bx, by, bw, bh = 120, 392, W-240, 10
        progress = max(0.0, 1.0 - remaining/max(total,1))

        # Track
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=5, fill=theme.bar_track)
        # Fill
        fw = int(bw * progress)
        if fw > 6:
            draw.rounded_rectangle([bx, by, bx+fw, by+bh], radius=5, fill=theme.accent)
            # Glow cap
            draw.ellipse([bx+fw-7, by-4, bx+fw+7, by+bh+4], fill=theme.accent2)

        # ── Quote ─────────────────────────────────────────────────────────────
        q  = _quote(remaining, total)
        qf = _f(22, light=True)
        draw.text((_cx(draw, q, qf, W), 422), q, font=qf, fill=theme.text_secondary)

        # ── Three stat pills ──────────────────────────────────────────────────
        pills = [
            (f"{total//60} MIN",  "TOTAL SESSION"),
            (f"{break_time} MIN", "BREAK AFTER"),
            (f"+10 XP",           "PER VOICE MIN"),
        ]
        pill_w, pill_h = 220, 72
        gap     = 30
        total_w = len(pills)*(pill_w+gap) - gap
        pill_x0 = (W - total_w) // 2

        for i, (val, label) in enumerate(pills):
            px = pill_x0 + i*(pill_w+gap)
            py = 476
            draw.rounded_rectangle([px, py, px+pill_w, py+pill_h], radius=12, fill=theme.panel_bg)
            # Left accent stripe
            draw.rounded_rectangle([px, py, px+3, py+pill_h], radius=2, fill=theme.accent)
            draw.text((_cx(draw, val,   _f(24, bold=True),   pill_w, px), py+10), val,   font=_f(24, bold=True),   fill=theme.text_primary)
            draw.text((_cx(draw, label, _f(11, medium=True), pill_w, px), py+44), label, font=_f(11, medium=True), fill=theme.text_secondary)

        # ── Pet section — right side ───────────────────────────────────────────
        if pet_key and pet_key in PIXEL_PETS:
            panel_x, panel_y = W-230, 88
            panel_w, panel_h = 190, 290
            # Panel
            draw.rounded_rectangle([panel_x, panel_y, panel_x+panel_w, panel_y+panel_h],
                                    radius=16, fill=theme.panel_bg)
            # Pet art centered in panel
            _draw_pet(draw, pet_key, panel_x + panel_w//2, panel_y + 120, 100)
            # Pet name
            name_str = pet_name or pet_key.replace("_"," ").title()
            nf = _f(16, bold=True)
            draw.text((_cx(draw, name_str, nf, panel_w, panel_x), panel_y+panel_h-44),
                      name_str, font=nf, fill=theme.accent)
            # Rarity
            rarity = PIXEL_PETS[pet_key]["rarity"]
            rf = _f(11, medium=True)
            rl = RARITY_LABELS[rarity]
            draw.text((_cx(draw, rl, rf, panel_w, panel_x), panel_y+panel_h-22),
                      rl, font=rf, fill=RARITY_COLORS[rarity])

        # ── Bottom rule + hint ────────────────────────────────────────────────
        draw.rectangle([44, H-50, W-44, H-49], fill=theme.bar_track)
        hint = "Stay in voice to earn XP and coins every minute"
        draw.text((_cx(draw, hint, _f(14, light=True), W), H-38),
                  hint, font=_f(14, light=True), fill=theme.text_secondary)

        return _to_bytes(img)

    # ── Pet Card ───────────────────────────────────────────────────────────────
    def render_pet_card(self, species: str, pet_name: str, level: int,
                        xp: int, happiness: int, active: bool = False) -> io.BytesIO:
        pdata  = PIXEL_PETS.get(species, list(PIXEL_PETS.values())[0])
        rarity = pdata["rarity"]
        rc     = RARITY_COLORS[rarity]
        W, H   = 600, 760

        # Pick a background that matches the pet's theme
        pet_bgs = {
            "bunny":      ((28,18,10),(42,26,14)),
            "fox":        ((26,14,5), (40,20,8)),
            "cat":        ((18,14,24),(28,20,38)),
            "wolf":       ((10,12,20),(16,18,32)),
            "owl":        ((16,10,4), (26,16,6)),
            "penguin":    ((6, 6, 14),(10,10,22)),
            "dragon":     ((4, 18,8), (8, 28,12)),
            "unicorn":    ((20,8, 26),(32,12,42)),
            "phoenix":    ((28,6, 2), (44,10,4)),
            "galaxy_cat": ((4, 2, 16),(8, 4, 28)),
        }
        bg1, bg2 = pet_bgs.get(species, ((12,12,20),(20,20,32)))

        img  = Image.new("RGB", (W,H), bg1)
        draw = ImageDraw.Draw(img)

        for y in range(H):
            draw.line([(0,y),(W,y)], fill=_lerp(bg1, bg2, y/H))

        # ── Subtle dot grid ───────────────────────────────────────────────────
        dot_col = _lerp(bg1, bg2, 1.6)
        for gx in range(0, W, 50):
            for gy in range(0, H, 50):
                draw.ellipse([gx-1,gy-1,gx+1,gy+1], fill=dot_col)

        # ── Top rarity glow ───────────────────────────────────────────────────
        glow = Image.new("RGBA", (W,H), (0,0,0,0))
        gd   = ImageDraw.Draw(glow)
        for radius in range(200, 0, -15):
            a = int(28*(1-radius/200))
            gd.ellipse([W//2-radius, -radius//2, W//2+radius, radius], fill=(*rc, a))
        img.paste(glow, mask=glow.split()[3])

        # ── Top bar + rarity badge ─────────────────────────────────────────────
        draw.rectangle([0, 0, W, 4], fill=rc)

        badge_text = RARITY_LABELS[rarity]
        bf  = _f(13, bold=True)
        bbb = draw.textbbox((0,0), badge_text, font=bf)
        bw  = bbb[2]-bbb[0]+36
        bx  = (W-bw)//2
        draw.rounded_rectangle([bx, 18, bx+bw, 46], radius=10, fill=rc)
        draw.text((_cx(draw, badge_text, bf, W), 24), badge_text, font=bf, fill=(8,8,8))

        # ── Pet illustration — large, centered ────────────────────────────────
        _draw_pet(draw, species, W//2, 220, 160)

        # ── Pet name — big, prominent ─────────────────────────────────────────
        nf = _f(52, bold=True)
        draw.text((_cx(draw, pet_name, nf, W), 370), pet_name, font=nf, fill=(245,245,255))

        # ── Species label ─────────────────────────────────────────────────────
        sp = species.replace("_"," ").upper()
        sf = _f(14, medium=True)
        draw.text((_cx(draw, sp, sf, W), 436), sp, font=sf, fill=rc)

        # ── Description ───────────────────────────────────────────────────────
        df = _f(15, light=True)
        draw.text((_cx(draw, pdata["desc"], df, W), 470), pdata["desc"], font=df, fill=(160,160,180))

        # ── Stats panel ───────────────────────────────────────────────────────
        px, py, pw, ph = 30, 510, W-60, 200
        draw.rounded_rectangle([px, py, px+pw, py+ph], radius=18, fill=_lerp(bg2,(0,0,0),0.3))
        draw.rounded_rectangle([px, py, px+pw, py+4],  radius=18, fill=rc)

        # Level
        lv_str = f"LV. {level}"
        draw.text((px+28, py+20), lv_str, font=_f(36, bold=True), fill=(245,245,255))

        # XP bar
        xp_need = level * 100
        bar_x, bar_y, bar_w, bar_h = px+28, py+76, pw-56, 10
        draw.text((bar_x, py+58), f"XP  {xp} / {xp_need}", font=_f(13, medium=True), fill=rc)
        draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], radius=5, fill=_lerp(bg1,(0,0,0),0.5))
        xfill = int(bar_w * min(xp/max(xp_need,1), 1))
        if xfill > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x+xfill, bar_y+bar_h], radius=5, fill=rc)

        # Happiness bar
        draw.text((bar_x, py+105), f"HAPPINESS  {happiness}%", font=_f(13, medium=True), fill=(100,200,120))
        hbar_y = py+126
        draw.rounded_rectangle([bar_x, hbar_y, bar_x+bar_w, hbar_y+bar_h], radius=5, fill=_lerp(bg1,(0,0,0),0.5))
        hcol  = (80,220,80) if happiness>60 else (220,160,40) if happiness>30 else (220,60,60)
        hfill = int(bar_w * happiness/100)
        if hfill > 0:
            draw.rounded_rectangle([bar_x, hbar_y, bar_x+hfill, hbar_y+bar_h], radius=5, fill=hcol)

        # Active badge
        if active:
            draw.rounded_rectangle([px+pw-150, py+20, px+pw-20, py+52], radius=10, fill=(30,190,70))
            draw.text((px+pw-138, py+28), "ACTIVE", font=_f(14, bold=True), fill=(255,255,255))

        # Pet ID hint
        id_hint = f"Use /renamepet to rename this companion"
        draw.text((_cx(draw, id_hint, _f(12, light=True), W), H-26),
                  id_hint, font=_f(12, light=True), fill=(80,80,100))

        return _to_bytes(img)

    # ── Pet Shop Card ──────────────────────────────────────────────────────────
    def render_pet_shop_card(self, species: str) -> io.BytesIO:
        pdata  = PIXEL_PETS.get(species, list(PIXEL_PETS.values())[0])
        rarity = pdata["rarity"]
        rc     = RARITY_COLORS[rarity]
        W, H   = 500, 480

        pet_bgs = {
            "bunny":      ((28,18,10),(42,26,14)),
            "fox":        ((26,14,5), (40,20,8)),
            "cat":        ((18,14,24),(28,20,38)),
            "wolf":       ((10,12,20),(16,18,32)),
            "owl":        ((16,10,4), (26,16,6)),
            "penguin":    ((6,6,14),  (10,10,22)),
            "dragon":     ((4,18,8),  (8,28,12)),
            "unicorn":    ((20,8,26), (32,12,42)),
            "phoenix":    ((28,6,2),  (44,10,4)),
            "galaxy_cat": ((4,2,16),  (8,4,28)),
        }
        bg1, bg2 = pet_bgs.get(species, ((12,12,20),(20,20,32)))

        img  = Image.new("RGB", (W,H), bg1)
        draw = ImageDraw.Draw(img)
        for y in range(H):
            draw.line([(0,y),(W,y)], fill=_lerp(bg1,bg2,y/H))

        # Dot grid
        dot_col = _lerp(bg1, bg2, 1.6)
        for gx in range(0, W, 50):
            for gy in range(0, H, 50):
                draw.ellipse([gx-1,gy-1,gx+1,gy+1], fill=dot_col)

        # Rarity glow
        glow = Image.new("RGBA", (W,H), (0,0,0,0))
        gd   = ImageDraw.Draw(glow)
        for rad in range(160, 0, -12):
            a = int(25*(1-rad/160))
            gd.ellipse([W//2-rad, -rad//2, W//2+rad, rad], fill=(*rc,a))
        img.paste(glow, mask=glow.split()[3])

        # Top bar
        draw.rectangle([0,0,W,4], fill=rc)

        # Rarity badge
        badge = RARITY_LABELS[rarity]
        bf    = _f(12, bold=True)
        bbb   = draw.textbbox((0,0), badge, font=bf)
        bw    = bbb[2]-bbb[0]+28
        bx    = (W-bw)//2
        draw.rounded_rectangle([bx,14,bx+bw,38], radius=9, fill=rc)
        draw.text((_cx(draw,badge,bf,W), 19), badge, font=bf, fill=(8,8,8))

        # Pet illustration
        _draw_pet(draw, species, W//2, 195, 140)

        # Name
        name = species.replace("_"," ").title()
        draw.text((_cx(draw,name,_f(32,bold=True),W), 320),
                  name, font=_f(32,bold=True), fill=(245,245,255))

        # Desc
        draw.text((_cx(draw, pdata["desc"], _f(14,light=True), W), 368),
                  pdata["desc"], font=_f(14,light=True), fill=(150,150,170))

        # Price tag
        price_str = f"{pdata['price']:,}  COINS"
        pf  = _f(20, bold=True)
        pbb = draw.textbbox((0,0), price_str, font=pf)
        pw  = pbb[2]-pbb[0]+48
        ppx = (W-pw)//2
        draw.rounded_rectangle([ppx, 408, ppx+pw, 448], radius=12, fill=_lerp(bg2,(0,0,0),0.5))
        draw.rounded_rectangle([ppx, 408, ppx+pw, 412], radius=12, fill=(200,170,40))
        draw.text((_cx(draw, price_str, pf, W), 416),
                  price_str, font=pf, fill=(220,185,55))

        return _to_bytes(img)

    # ── Profile Card ──────────────────────────────────────────────────────────
    def render_profile(self, username: str, xp: int, coins: int,
                       total_focus: int, sessions: int,
                       active_pet: dict = None) -> io.BytesIO:
        W, H = 960, 520
        bg1  = (6, 6, 14)
        bg2  = (10, 10, 22)
        acc  = (100, 130, 255)

        img  = Image.new("RGB", (W,H), bg1)
        draw = ImageDraw.Draw(img)
        for y in range(H):
            draw.line([(0,y),(W,y)], fill=_lerp(bg1,bg2,y/H))

        # Dot grid
        for gx in range(0,W,60):
            for gy in range(0,H,60):
                draw.ellipse([gx-1,gy-1,gx+1,gy+1], fill=(16,16,32))

        # Top bar
        draw.rectangle([0,0,W,4], fill=acc)

        # ── Left column — user info ────────────────────────────────────────────
        col_x = 48

        # Username
        draw.text((col_x, 30), username, font=_f(48, bold=True), fill=(250,250,255))

        # Level + badge
        level   = max(1, int(xp**0.45)//5)
        lv_str  = f"LEVEL  {level}"
        draw.text((col_x, 92), lv_str, font=_f(16, medium=True), fill=acc)

        # XP progress bar
        xp_next = int(((level+1)*5)**(1/0.45))
        xp_prev = int((level*5)**(1/0.45)) if level > 1 else 0
        xp_bar_w = 360
        xp_fill  = int(xp_bar_w * min((xp-xp_prev)/max(xp_next-xp_prev,1), 1))
        draw.text((col_x, 122), f"{xp:,} XP  /  {xp_next:,} to next level",
                  font=_f(12, light=True), fill=(100,110,160))
        bary = 146
        draw.rounded_rectangle([col_x, bary, col_x+xp_bar_w, bary+8], radius=4, fill=(18,20,42))
        if xp_fill > 2:
            draw.rounded_rectangle([col_x, bary, col_x+xp_fill, bary+8], radius=4, fill=acc)

        # ── 4 stat cards ──────────────────────────────────────────────────────
        card_w, card_h = 188, 120
        cards = [
            ("TOTAL XP",     f"{xp:,}",              acc),
            ("COINS",        f"{coins:,}",            (210,175,35)),
            ("HOURS FOCUSED",f"{total_focus/60:.1f}", (55,195,110)),
            ("SESSIONS",     str(sessions),           (185,90,230)),
        ]
        card_row_y = 185
        for i, (label, val, col) in enumerate(cards):
            cx2  = col_x + i*(card_w+14)
            # Card bg
            draw.rounded_rectangle([cx2, card_row_y, cx2+card_w, card_row_y+card_h],
                                    radius=14, fill=(13,15,32))
            # Top accent
            draw.rounded_rectangle([cx2, card_row_y, cx2+card_w, card_row_y+4],
                                    radius=14, fill=col)
            # Value
            draw.text((cx2+18, card_row_y+18), val,
                      font=_f(30, bold=True), fill=(245,245,255))
            # Label
            draw.text((cx2+18, card_row_y+62), label,
                      font=_f(11, medium=True), fill=(90,100,140))
            # Bottom micro bar (decorative)
            draw.rounded_rectangle([cx2+18, card_row_y+88, cx2+card_w-18, card_row_y+92],
                                    radius=3, fill=_lerp((13,15,32), col, 0.4))

        # ── Focus progress bar ─────────────────────────────────────────────────
        fbar_y  = 342
        fbar_w  = card_w*4+14*3
        draw.text((col_x, fbar_y), "FOCUS PROGRESS",
                  font=_f(11, medium=True), fill=(80,90,130))
        draw.rounded_rectangle([col_x, fbar_y+24, col_x+fbar_w, fbar_y+36],
                                radius=6, fill=(14,16,36))
        fill_hrs = min(total_focus/60, 100)/100
        ffw = int(fbar_w * fill_hrs)
        if ffw > 2:
            draw.rounded_rectangle([col_x, fbar_y+24, col_x+ffw, fbar_y+36],
                                    radius=6, fill=(55,195,110))
        for pct_val, label in [(0.1,"10h"),(0.25,"25h"),(0.5,"50h"),(1.0,"100h")]:
            mx = col_x + int(fbar_w*pct_val)
            draw.line([(mx,fbar_y+20),(mx,fbar_y+40)], fill=(28,32,60))
            draw.text((mx-10, fbar_y+42), label, font=_f(10, light=True), fill=(70,80,120))

        # ── Achievements row (placeholder cards) ──────────────────────────────
        ach_y = 416
        draw.text((col_x, ach_y), "MILESTONES", font=_f(11, medium=True), fill=(80,90,130))

        milestones = [
            ("First Session",  sessions >= 1,  acc),
            ("10 Sessions",    sessions >= 10, (55,195,110)),
            ("50 Hours",       total_focus >= 3000, (210,175,35)),
            ("1000 XP",        xp >= 1000, (185,90,230)),
        ]
        for i,(name,unlocked,col) in enumerate(milestones):
            mx2 = col_x + i*200
            tile_col = col if unlocked else (16,18,36)
            draw.rounded_rectangle([mx2, ach_y+24, mx2+182, ach_y+60],
                                    radius=8, fill=tile_col)
            text_col = (8,8,8) if unlocked else (50,55,80)
            draw.text((mx2+14, ach_y+36), name, font=_f(13, medium=True), fill=text_col)

        # ── Right panel — active pet ───────────────────────────────────────────
        if active_pet:
            species  = active_pet.get("species","cat")
            pdata    = PIXEL_PETS.get(species, list(PIXEL_PETS.values())[0])
            rarity   = pdata["rarity"]
            rc       = RARITY_COLORS[rarity]
            panel_x  = W - 240
            panel_y  = 30
            panel_w  = 200
            panel_h  = H - 60

            draw.rounded_rectangle([panel_x, panel_y, panel_x+panel_w, panel_y+panel_h],
                                    radius=18, fill=(12,14,28))
            draw.rounded_rectangle([panel_x, panel_y, panel_x+panel_w, panel_y+4],
                                    radius=18, fill=rc)

            draw.text((_cx(draw,"PET",_f(11,medium=True),panel_w,panel_x), panel_y+16),
                      "PET", font=_f(11,medium=True), fill=(80,90,130))

            # Pet art
            _draw_pet(draw, species, panel_x + panel_w//2, panel_y + 190, 130)

            # Name
            pname = active_pet.get("name", species.title())
            draw.text((_cx(draw, pname, _f(20,bold=True), panel_w, panel_x), panel_y+308),
                      pname, font=_f(20,bold=True), fill=(245,245,255))

            # Rarity label
            draw.text((_cx(draw, RARITY_LABELS[rarity], _f(11,medium=True), panel_w, panel_x), panel_y+338),
                      RARITY_LABELS[rarity], font=_f(11,medium=True), fill=rc)

            # Level
            lv2 = active_pet.get("level",1)
            draw.text((_cx(draw, f"LEVEL  {lv2}", _f(14,medium=True), panel_w, panel_x), panel_y+364),
                      f"LEVEL  {lv2}", font=_f(14,medium=True), fill=acc)

            # Mini XP bar
            pxp   = active_pet.get("xp",0)
            pxpn  = lv2 * 100
            mbx   = panel_x + 20
            mbw   = panel_w - 40
            mby   = panel_y + 396
            draw.rounded_rectangle([mbx, mby, mbx+mbw, mby+6], radius=3, fill=(18,20,42))
            mf = int(mbw * min(pxp/max(pxpn,1),1))
            if mf > 0:
                draw.rounded_rectangle([mbx, mby, mbx+mf, mby+6], radius=3, fill=rc)

        # Footer
        draw.rectangle([0, H-40, W, H-39], fill=(18,20,42))
        footer = "Use /timer to earn XP and coins  //  /petshop to adopt companions"
        draw.text((_cx(draw,footer,_f(12,light=True),W), H-28),
                  footer, font=_f(12,light=True), fill=(60,70,100))

        return _to_bytes(img)
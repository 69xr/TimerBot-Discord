"""
Image Engine — Generates all dynamic images for FocusBeast.
Timer frames, pet cards, profile cards — all rendered here.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import math
import random
from dataclasses import dataclass
from typing import Tuple

# ── Theme Definitions ─────────────────────────────────────────────────────────
@dataclass
class Theme:
    name: str
    emoji: str
    discord_color: int
    bg: Tuple[int, int, int]
    bg2: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    accent2: Tuple[int, int, int]
    text: Tuple[int, int, int]
    glow: Tuple[int, int, int]

THEMES = {
    "lofi": Theme(
        "lofi", "🎵", 0x7C5CBF,
        (18, 12, 30), (30, 18, 48),
        (160, 100, 240), (220, 150, 255),
        (230, 210, 255), (140, 80, 220),
    ),
    "nature": Theme(
        "nature", "🌿", 0x2D7D46,
        (8, 24, 12), (12, 40, 18),
        (50, 180, 80), (120, 230, 100),
        (180, 255, 190), (40, 160, 70),
    ),
    "space": Theme(
        "space", "🚀", 0x1A1A6E,
        (3, 3, 18), (8, 8, 35),
        (60, 80, 255), (120, 160, 255),
        (200, 215, 255), (50, 70, 220),
    ),
    "ocean": Theme(
        "ocean", "🌊", 0x0077AA,
        (3, 15, 35), (5, 25, 55),
        (0, 160, 230), (80, 210, 255),
        (160, 235, 255), (0, 130, 200),
    ),
    "fire": Theme(
        "fire", "🔥", 0xDD3300,
        (30, 6, 3), (50, 12, 5),
        (255, 70, 10), (255, 160, 40),
        (255, 215, 160), (220, 50, 10),
    ),
    "minimal": Theme(
        "minimal", "⚡", 0x303030,
        (12, 12, 12), (20, 20, 20),
        (200, 200, 200), (255, 255, 255),
        (240, 240, 240), (160, 160, 160),
    ),
    "pastel": Theme(
        "pastel", "🌸", 0xE88FA8,
        (45, 28, 38), (60, 35, 50),
        (255, 150, 180), (255, 200, 215),
        (255, 230, 240), (230, 120, 160),
    ),
    "cyberpunk": Theme(
        "cyberpunk", "⚡", 0xFF00FF,
        (5, 3, 15), (10, 5, 25),
        (255, 0, 220), (0, 255, 210),
        (255, 220, 255), (180, 0, 255),
    ),
    "aurora": Theme(
        "aurora", "🌌", 0x00C8A0,
        (5, 15, 20), (8, 25, 35),
        (0, 200, 160), (100, 255, 200),
        (200, 255, 240), (0, 170, 140),
    ),
    "golden": Theme(
        "golden", "👑", 0xD4A010,
        (25, 18, 5), (40, 28, 8),
        (220, 170, 20), (255, 215, 80),
        (255, 245, 200), (190, 140, 10),
    ),
}

# ── Pet Definitions ───────────────────────────────────────────────────────────
PETS = {
    # Common
    "fox": {
        "rarity": "common", "emoji": "🦊",
        "color": (220, 120, 40), "bg": (40, 20, 10), "accent": (255, 150, 60),
        "desc": "Clever and quick. Loves focus sessions.",
        "price": 200
    },
    "cat": {
        "rarity": "common", "emoji": "🐱",
        "color": (200, 180, 160), "bg": (30, 25, 20), "accent": (240, 210, 180),
        "desc": "Mysterious and calm. Purrs during your grind.",
        "price": 200
    },
    "bunny": {
        "rarity": "common", "emoji": "🐰",
        "color": (230, 210, 210), "bg": (35, 20, 25), "accent": (255, 180, 200),
        "desc": "Energetic and supportive. Hops when you're productive.",
        "price": 150
    },
    # Uncommon
    "wolf": {
        "rarity": "uncommon", "emoji": "🐺",
        "color": (140, 140, 160), "bg": (15, 15, 25), "accent": (180, 180, 220),
        "desc": "Loyal guardian. Howls at the moon for you.",
        "price": 500
    },
    "owl": {
        "rarity": "uncommon", "emoji": "🦉",
        "color": (160, 130, 80), "bg": (20, 15, 10), "accent": (210, 180, 100),
        "desc": "Wise companion. Boosts your focus aura.",
        "price": 500
    },
    "penguin": {
        "rarity": "uncommon", "emoji": "🐧",
        "color": (40, 40, 50), "bg": (10, 10, 20), "accent": (120, 160, 255),
        "desc": "Chill vibes. Keeps you cool under pressure.",
        "price": 450
    },
    # Rare
    "dragon": {
        "rarity": "rare", "emoji": "🐉",
        "color": (60, 180, 80), "bg": (5, 25, 10), "accent": (100, 255, 120),
        "desc": "Ancient power. XP gains are doubled.",
        "price": 1500
    },
    "unicorn": {
        "rarity": "rare", "emoji": "🦄",
        "color": (220, 120, 220), "bg": (25, 10, 30), "accent": (255, 180, 255),
        "desc": "Magical focus. Every session sparkles.",
        "price": 1500
    },
    # Legendary
    "phoenix": {
        "rarity": "legendary", "emoji": "🔥",
        "color": (255, 120, 0), "bg": (40, 10, 0), "accent": (255, 200, 0),
        "desc": "Reborn from focus. The ultimate grind companion.",
        "price": 5000
    },
    "galaxy_cat": {
        "rarity": "legendary", "emoji": "🌌",
        "color": (100, 60, 200), "bg": (5, 3, 20), "accent": (180, 120, 255),
        "desc": "Cosmic entity. Exists across all study dimensions.",
        "price": 5000
    },
}

RARITY_COLORS = {
    "common":    (160, 160, 160),
    "uncommon":  (60, 200, 80),
    "rare":      (60, 120, 255),
    "legendary": (255, 160, 0),
}

RARITY_BADGES = {
    "common":    "COMMON",
    "uncommon":  "UNCOMMON",
    "rare":      "RARE ✦",
    "legendary": "LEGENDARY ★",
}


# ── Font loader ────────────────────────────────────────────────────────────────
def _font(size: int, bold=False):
    paths = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()


def _center_x(draw, text, font, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    return (width - (bbox[2] - bbox[0])) // 2


def _lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class ImageEngine:

    # ─── Timer Frame ──────────────────────────────────────────────────────────
    def render_timer(
        self,
        theme_name: str,
        remaining: int,
        total: int,
        break_time: int,
        pet_emoji: str = None,
        pet_name: str = None,
    ) -> io.BytesIO:
        theme = THEMES.get(theme_name, THEMES["minimal"])
        W, H = 900, 460

        img = Image.new("RGB", (W, H), theme.bg)
        draw = ImageDraw.Draw(img)

        # ── Gradient background ──────────────────────────────────────────────
        for y in range(H):
            t = y / H
            c = _lerp_color(theme.bg, theme.bg2, t)
            draw.line([(0, y), (W, y)], fill=c)

        # ── Decorative glow circles ───────────────────────────────────────────
        glow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        for cx, cy, r, a in [
            (W - 80, 60, 120, 35),
            (80, H - 60, 100, 25),
            (W // 2, H // 2, 200, 15),
        ]:
            for dr in range(r, 0, -8):
                alpha = int(a * (1 - dr / r))
                glow_draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr],
                                   fill=(*theme.glow, alpha))
        img.paste(glow_img, mask=glow_img.split()[3])

        # ── Grid lines (subtle) ───────────────────────────────────────────────
        for x in range(0, W, 60):
            draw.line([(x, 0), (x, H)], fill=(*theme.accent, 8) if len(theme.accent) == 3 else theme.accent[:3])
        for y in range(0, H, 60):
            draw.line([(0, y), (W, y)], fill=(*theme.accent, 8) if len(theme.accent) == 3 else theme.accent[:3])

        # ── Top bar ───────────────────────────────────────────────────────────
        draw.rectangle([0, 0, W, 60], fill=(*theme.accent, 25) if False else theme.bg2)
        top_text = f"{theme.emoji}  {theme_name.upper()} FOCUS"
        draw.text((30, 18), top_text, font=_font(22, bold=True), fill=theme.accent)

        # Session info top right
        pct = int((1 - remaining / max(total, 1)) * 100)
        draw.text((W - 130, 18), f"{pct}% done", font=_font(20), fill=theme.text)

        # ── Big countdown ─────────────────────────────────────────────────────
        mins, secs = remaining // 60, remaining % 60
        timer_str = f"{mins:02d}:{secs:02d}"

        # Shadow
        draw.text((_center_x(draw, timer_str, _font(110, bold=True), W) + 3, 83),
                  timer_str, font=_font(110, bold=True), fill=theme.bg)
        # Main
        draw.text((_center_x(draw, timer_str, _font(110, bold=True), W), 80),
                  timer_str, font=_font(110, bold=True), fill=theme.text)

        # ── Progress bar ──────────────────────────────────────────────────────
        bx, by, bw, bh = 50, 280, W - 100, 22
        # Track
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=11, fill=theme.bg2)
        # Fill
        fill = int(bw * (1 - remaining / max(total, 1)))
        if fill > 4:
            draw.rounded_rectangle([bx, by, bx + fill, by + bh], radius=11, fill=theme.accent)
            # Shimmer on fill end
            draw.ellipse([bx + fill - 8, by - 3, bx + fill + 8, by + bh + 3],
                         fill=theme.accent2)

        # ── Stats row ─────────────────────────────────────────────────────────
        draw.text((50, 325), f"⏱  Total: {total // 60}m", font=_font(20), fill=theme.text)
        draw.text((W // 2 - 50, 325), f"☕  Break: {break_time}m", font=_font(20), fill=theme.text)

        # ── Pet section ───────────────────────────────────────────────────────
        if pet_emoji and pet_name:
            pet_box_x = W - 200
            draw.rounded_rectangle(
                [pet_box_x, H - 100, W - 20, H - 20],
                radius=12, fill=theme.bg2
            )
            draw.text((pet_box_x + 14, H - 90), pet_emoji, font=_font(30), fill=theme.text)
            draw.text((pet_box_x + 55, H - 88), pet_name, font=_font(18, bold=True), fill=theme.accent2)
            draw.text((pet_box_x + 55, H - 65), "studying with you", font=_font(13), fill=theme.text)

        # ── Bottom hint ───────────────────────────────────────────────────────
        draw.text((50, H - 36), "🎯 Stay focused. +10 XP/min in voice.", font=_font(15), fill=(*theme.text[:3],))

        return self._to_bytes(img)

    # ─── Pet Card ──────────────────────────────────────────────────────────────
    def render_pet_card(self, species: str, pet_name: str, level: int, xp: int, happiness: int, active: bool = False) -> io.BytesIO:
        pet = PETS.get(species, PETS["cat"])
        rarity = pet["rarity"]
        rcolor = RARITY_COLORS[rarity]
        W, H = 500, 600

        img = Image.new("RGB", (W, H), pet["bg"])
        draw = ImageDraw.Draw(img)

        # ── Gradient ─────────────────────────────────────────────────────────
        for y in range(H):
            t = y / H
            bg2 = tuple(min(255, int(c * 1.5)) for c in pet["bg"])
            c = _lerp_color(pet["bg"], bg2, t * 0.6)
            draw.line([(0, y), (W, y)], fill=c)

        # ── Rarity glow at top ────────────────────────────────────────────────
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(glow)
        for r in range(160, 0, -10):
            alpha = int(40 * (1 - r / 160))
            g_draw.ellipse([W // 2 - r, -r // 2, W // 2 + r, r], fill=(*rcolor, alpha))
        img.paste(glow, mask=glow.split()[3])

        # ── Rarity badge ─────────────────────────────────────────────────────
        badge_text = RARITY_BADGES[rarity]
        bw = 160 if rarity == "legendary" else 130
        bx = (W - bw) // 2
        draw.rounded_rectangle([bx, 20, bx + bw, 48], radius=12, fill=rcolor)
        draw.text((_center_x(draw, badge_text, _font(14, bold=True), W), 26),
                  badge_text, font=_font(14, bold=True), fill=(10, 10, 10))

        # ── Big emoji ────────────────────────────────────────────────────────
        emoji_text = pet["emoji"]
        draw.text((_center_x(draw, emoji_text, _font(120), W), 70),
                  emoji_text, font=_font(120), fill=pet["color"])

        # ── Pet name with custom font ──────────────────────────────────────────
        draw.text((_center_x(draw, pet_name, _font(42, bold=True), W), 215),
                  pet_name, font=_font(42, bold=True), fill=pet["accent"])

        # ── Species ───────────────────────────────────────────────────────────
        species_str = f"— {species.replace('_', ' ').upper()} —"
        draw.text((_center_x(draw, species_str, _font(16), W), 268),
                  species_str, font=_font(16), fill=rcolor)

        # ── Description ───────────────────────────────────────────────────────
        desc = pet["desc"]
        draw.text((_center_x(draw, desc, _font(15), W), 305),
                  desc, font=_font(15), fill=(180, 180, 180))

        # ── Stats panel ───────────────────────────────────────────────────────
        draw.rounded_rectangle([30, 350, W - 30, 530], radius=16,
                                fill=tuple(min(255, c + 10) for c in pet["bg"]))

        # Level
        draw.text((60, 375), "LEVEL", font=_font(13, bold=True), fill=rcolor)
        draw.text((60, 396), str(level), font=_font(36, bold=True), fill=pet["accent"])

        # XP bar
        xp_needed = level * 100
        draw.text((160, 375), f"XP  {xp}/{xp_needed}", font=_font(13, bold=True), fill=rcolor)
        draw.rounded_rectangle([160, 400, W - 60, 420], radius=6, fill=pet["bg"])
        xp_fill = int((W - 220) * min(xp / xp_needed, 1))
        if xp_fill > 0:
            draw.rounded_rectangle([160, 400, 160 + xp_fill, 420], radius=6, fill=pet["accent"])

        # Happiness bar
        draw.text((60, 440), "😊 Happiness", font=_font(14, bold=True), fill=rcolor)
        draw.rounded_rectangle([60, 465, W - 60, 483], radius=6, fill=pet["bg"])
        hap_fill = int((W - 120) * happiness / 100)
        hap_color = (80, 220, 80) if happiness > 60 else (220, 160, 40) if happiness > 30 else (220, 60, 60)
        if hap_fill > 0:
            draw.rounded_rectangle([60, 465, 60 + hap_fill, 483], radius=6, fill=hap_color)
        draw.text((W - 100, 465), f"{happiness}%", font=_font(13), fill=hap_color)

        # Active badge
        if active:
            draw.rounded_rectangle([30, 540, 160, 568], radius=10, fill=(40, 200, 80))
            draw.text((45, 547), "✦ ACTIVE", font=_font(14, bold=True), fill=(255, 255, 255))

        return self._to_bytes(img)

    # ─── Shop Pet Listing ─────────────────────────────────────────────────────
    def render_pet_shop_card(self, species: str) -> io.BytesIO:
        pet = PETS[species]
        rarity = pet["rarity"]
        rcolor = RARITY_COLORS[rarity]
        W, H = 400, 340

        img = Image.new("RGB", (W, H), pet["bg"])
        draw = ImageDraw.Draw(img)

        for y in range(H):
            t = y / H
            bg2 = tuple(min(255, int(c * 2)) for c in pet["bg"])
            c = _lerp_color(pet["bg"], bg2, t * 0.5)
            draw.line([(0, y), (W, y)], fill=c)

        # Border glow
        for bw in range(3, 0, -1):
            draw.rectangle([bw, bw, W - bw, H - bw], outline=(*rcolor, 80 - bw * 20))

        # Rarity
        draw.rounded_rectangle([W // 2 - 55, 12, W // 2 + 55, 36], radius=10, fill=rcolor)
        draw.text((_center_x(draw, RARITY_BADGES[rarity], _font(12, bold=True), W), 16),
                  RARITY_BADGES[rarity], font=_font(12, bold=True), fill=(10, 10, 10))

        # Emoji
        draw.text((_center_x(draw, pet["emoji"], _font(80), W), 44),
                  pet["emoji"], font=_font(80), fill=pet["color"])

        # Name
        name = species.replace("_", " ").title()
        draw.text((_center_x(draw, name, _font(26, bold=True), W), 148),
                  name, font=_font(26, bold=True), fill=pet["accent"])

        # Desc
        draw.text((_center_x(draw, pet["desc"], _font(13), W), 188),
                  pet["desc"], font=_font(13), fill=(170, 170, 170))

        # Price
        price_str = f"🪙  {pet['price']:,} coins"
        draw.rounded_rectangle([W // 2 - 80, 240, W // 2 + 80, 272], radius=12,
                                fill=tuple(min(255, c + 25) for c in pet["bg"]))
        draw.text((_center_x(draw, price_str, _font(16, bold=True), W), 247),
                  price_str, font=_font(16, bold=True), fill=(220, 190, 80))

        return self._to_bytes(img)

    # ─── Profile Card ────────────────────────────────────────────────────────
    def render_profile(self, username: str, xp: int, coins: int,
                       total_focus: int, sessions: int,
                       active_pet: dict = None) -> io.BytesIO:
        W, H = 700, 380
        bg = (10, 10, 20)
        accent = (80, 140, 255)
        gold = (220, 180, 50)

        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)

        for y in range(H):
            t = y / H
            c = _lerp_color(bg, (15, 15, 35), t)
            draw.line([(0, y), (W, y)], fill=c)

        # Left accent bar
        for x in range(6):
            alpha = 255 - x * 40
            draw.rectangle([x, 0, x, H], fill=(*accent, alpha) if False else accent)

        # Username
        draw.text((40, 35), username, font=_font(36, bold=True), fill=(255, 255, 255))
        draw.text((40, 82), "Focus Beast Profile", font=_font(16), fill=(120, 120, 160))

        # Stats grid
        stats = [
            ("⭐ XP", f"{xp:,}", accent),
            ("🪙 Coins", f"{coins:,}", gold),
            ("⏱ Hours", f"{total_focus // 60:.1f}h", (80, 200, 120)),
            ("📚 Sessions", str(sessions), (200, 100, 220)),
        ]
        for i, (label, val, color) in enumerate(stats):
            x = 40 + (i % 2) * 310
            y = 140 + (i // 2) * 80
            draw.rounded_rectangle([x, y, x + 280, y + 60], radius=10,
                                    fill=(20, 20, 35))
            draw.text((x + 16, y + 10), label, font=_font(13), fill=(160, 160, 180))
            draw.text((x + 16, y + 30), val, font=_font(22, bold=True), fill=color)

        # Pet preview
        if active_pet:
            pet_data = PETS.get(active_pet["species"], {})
            pet_emoji = pet_data.get("emoji", "?")
            pet_accent = pet_data.get("accent", accent)
            draw.rounded_rectangle([W - 200, 60, W - 20, 200], radius=14,
                                    fill=(20, 20, 35))
            draw.text((W - 190, 70), pet_emoji, font=_font(60), fill=pet_accent)
            draw.text((W - 190, 142), active_pet["name"], font=_font(16, bold=True), fill=pet_accent)
            lv = f"Lv.{active_pet['level']}"
            draw.text((W - 190, 168), lv, font=_font(14), fill=(140, 140, 160))
            draw.rounded_rectangle([W - 200, 208, W - 20, 230], radius=6,
                                    fill=(30, 30, 50))
            rarity = pet_data.get("rarity", "common")
            draw.text((W - 190, 212), RARITY_BADGES[rarity], font=_font(13, bold=True),
                      fill=RARITY_COLORS[rarity])

        draw.text((40, H - 30), "🔥 Keep grinding!", font=_font(14), fill=(80, 80, 100))

        return self._to_bytes(img)

    # ─── Helpers ─────────────────────────────────────────────────────────────
    def _to_bytes(self, img: Image.Image) -> io.BytesIO:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf
"""
Dice Orb Renderer - Animated rolling GIF
Numbers roll down through the crystal ball and land on the result
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import io
import random

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
ORB_PATH = os.path.join(ASSETS_DIR, 'dice_orb.png')

# Crystal center - centered in the purple orb glass
ORB_CENTER_X = 566
ORB_CENTER_Y = 580

DARK_BG = (47, 49, 54)
GIF_SIZE = (300, 368)

# Gold color palette
GOLD_BRIGHT = (255, 215, 0, 255)
GOLD_DARK = (200, 165, 0, 255)
GOLD_GLOW = (255, 200, 50, 100)
GOLD_SHADOW = (120, 90, 0, 180)

_font_cache = {}


def _get_font(size):
    if size not in _font_cache:
        # Try Georgia Bold for elegant serif look, fallback chain
        for path in [
            "assets/fonts/georgiab.ttf",
            "assets/fonts/georgiab.ttf",
            "assets/fonts/arialbd.ttf",
        ]:
            try:
                _font_cache[size] = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def _prepare_orb():
    """Load orb with dark background"""
    img = Image.open(ORB_PATH).convert('RGBA')
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 20 or (r > 220 and g > 220 and b > 220):
                pixels[x, y] = (*DARK_BG, 255)
            elif a < 240:
                blend = a / 255
                nr = int(r * blend + DARK_BG[0] * (1 - blend))
                ng = int(g * blend + DARK_BG[1] * (1 - blend))
                nb = int(b * blend + DARK_BG[2] * (1 - blend))
                pixels[x, y] = (nr, ng, nb, 255)
            elif r > 180 and g > 180 and b > 180:
                brightness = (r + g + b) / 3
                blend = max(0, (brightness - 180) / 75)
                nr = int(r * (1 - blend) + DARK_BG[0] * blend)
                ng = int(g * (1 - blend) + DARK_BG[1] * blend)
                nb = int(b * (1 - blend) + DARK_BG[2] * blend)
                pixels[x, y] = (nr, ng, nb, 255)
    return img


_orb_base = None


def _get_orb():
    global _orb_base
    if _orb_base is None:
        _orb_base = _prepare_orb()
    return _orb_base.copy()


def _draw_number(draw, text, cx, cy, font, text_color, glow_color, shadow_color):
    """Draw a number with glow and shadow effects"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = cx - text_w // 2
    y = cy - text_h // 2

    # Outer glow
    for dx in range(-5, 6, 2):
        for dy in range(-5, 6, 2):
            if abs(dx) + abs(dy) > 2:
                draw.text((x + dx, y + dy), text, fill=glow_color, font=font)

    # Drop shadow
    draw.text((x + 4, y + 4), text, fill=shadow_color, font=font)

    # Main text with slight 3D effect
    draw.text((x + 1, y + 1), text, fill=text_color, font=font)
    draw.text((x, y), text, fill=text_color, font=font)


def _render_frame(number, y_offset=0, text_color=GOLD_BRIGHT, glow_color=GOLD_GLOW,
                  shadow_color=GOLD_SHADOW, small=False, alpha=255):
    """Render a single frame with number at a y offset (for rolling effect)"""
    img = _get_orb()
    draw = ImageDraw.Draw(img)
    text = str(number)

    font_size = 240 if len(text) < 3 else 190
    font = _get_font(font_size)

    # Apply alpha to text colors for fade effect
    if alpha < 255:
        text_color = (*text_color[:3], alpha)
        glow_color = (*glow_color[:3], min(alpha, glow_color[3]))

    _draw_number(draw, text, ORB_CENTER_X, ORB_CENTER_Y + y_offset,
                 font, text_color, glow_color, shadow_color)

    if small:
        img = img.resize(GIF_SIZE, Image.LANCZOS)
    return img


def render_orb_gif(final_number, color=None):
    """
    Animated GIF: numbers roll down through the crystal,
    slow down, and land on the final result.
    """
    # Final number color
    if color == 'green':
        final_text = (80, 255, 120, 255)
        final_glow = (40, 200, 70, 100)
        final_shadow = (20, 80, 30, 180)
    elif color == 'red':
        final_text = (255, 80, 80, 255)
        final_glow = (200, 40, 40, 100)
        final_shadow = (100, 20, 20, 180)
    else:
        final_text = GOLD_BRIGHT
        final_glow = GOLD_GLOW
        final_shadow = GOLD_SHADOW

    frames = []
    durations = []

    # Build a shared palette from the final frame for consistent colors
    final_frame = _render_frame(final_number, y_offset=0,
                                text_color=final_text, glow_color=final_glow,
                                shadow_color=final_shadow, small=True)
    palette_img = final_frame.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    palette = palette_img.getpalette()

    # Phase 1: Fast spin (5 frames)
    for _ in range(5):
        n = random.randint(1, 100)
        frame = _render_frame(n, y_offset=0, small=True)
        q = frame.convert('RGB').quantize(palette=palette_img, dither=Image.Dither.NONE)
        frames.append(q)
        durations.append(80)

    # Phase 2: Slowing down (3 frames)
    for delay in [150, 300, 500]:
        n = random.randint(1, 100)
        frame = _render_frame(n, y_offset=0, small=True)
        q = frame.convert('RGB').quantize(palette=palette_img, dither=Image.Dither.NONE)
        frames.append(q)
        durations.append(delay)

    # Phase 3: Final number
    frames.append(palette_img)
    durations.append(3000)

    buf = io.BytesIO()
    frames[0].save(
        buf, format='GIF', save_all=True,
        append_images=frames[1:],
        duration=durations, loop=0, optimize=False
    )
    buf.seek(0)
    return buf


def render_orb(number, color=None):
    """Static PNG fallback"""
    if color == 'green':
        tc, gc, sc = (80, 255, 120, 255), (40, 200, 70, 100), (20, 80, 30, 180)
    elif color == 'red':
        tc, gc, sc = (255, 80, 80, 255), (200, 40, 40, 100), (100, 20, 20, 180)
    else:
        tc, gc, sc = GOLD_BRIGHT, GOLD_GLOW, GOLD_SHADOW

    img = _render_frame(number, text_color=tc, glow_color=gc, shadow_color=sc)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

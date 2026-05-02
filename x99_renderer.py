"""
99x Frame Renderer - Shows the rolled number in the purple frame
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io
import random

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
FRAME_PATH = os.path.join(ASSETS_DIR, '99x_frame.png')

# Center of the purple area (below the X99 text)
FRAME_CENTER_X = 627
FRAME_CENTER_Y = 670

DARK_BG = (47, 49, 54)
GIF_SIZE = (350, 350)

_font_cache = {}


def _get_font(size):
    if size not in _font_cache:
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


_frame_base = None


def _get_frame():
    global _frame_base
    if _frame_base is None:
        img = Image.open(FRAME_PATH).convert('RGBA')
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
                    blend2 = max(0, (brightness - 180) / 75)
                    nr = int(r * (1 - blend2) + DARK_BG[0] * blend2)
                    ng = int(g * (1 - blend2) + DARK_BG[1] * blend2)
                    nb = int(b * (1 - blend2) + DARK_BG[2] * blend2)
                    pixels[x, y] = (nr, ng, nb, 255)
        _frame_base = img
    return _frame_base.copy()


def _render_frame(number, text_color, glow_color, shadow_color, small=False):
    img = _get_frame()
    draw = ImageDraw.Draw(img)
    text = str(number)

    font_size = 280 if len(text) < 3 else 220
    font = _get_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = FRAME_CENTER_X - text_w // 2
    y = FRAME_CENTER_Y - text_h // 2

    # Glow
    for dx in range(-5, 6, 2):
        for dy in range(-5, 6, 2):
            if abs(dx) + abs(dy) > 2:
                draw.text((x + dx, y + dy), text, fill=glow_color, font=font)

    draw.text((x + 4, y + 4), text, fill=shadow_color, font=font)
    draw.text((x, y), text, fill=text_color, font=font)

    if small:
        img = img.resize(GIF_SIZE, Image.LANCZOS)
    return img


GOLD_BRIGHT = (255, 215, 0, 255)
GOLD_GLOW = (255, 200, 50, 100)
GOLD_SHADOW = (120, 90, 0, 180)


def render_99x_gif(final_number, color=None):
    """Animated GIF for 99x game"""
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

    spin_text = (255, 255, 255, 255)
    spin_glow = (200, 200, 200, 80)
    spin_shadow = (80, 80, 80, 180)

    frames = []
    durations = []

    # Build palette from final frame
    final_frame = _render_frame(final_number, final_text, final_glow, final_shadow, small=True)
    palette_img = final_frame.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT)

    # Fast spin (5 frames)
    for _ in range(5):
        n = random.randint(1, 100)
        frame = _render_frame(n, spin_text, spin_glow, spin_shadow, small=True)
        q = frame.convert('RGB').quantize(palette=palette_img, dither=Image.Dither.NONE)
        frames.append(q)
        durations.append(80)

    # Slowing (3 frames)
    for delay in [150, 300, 500]:
        n = random.randint(1, 100)
        frame = _render_frame(n, spin_text, spin_glow, spin_shadow, small=True)
        q = frame.convert('RGB').quantize(palette=palette_img, dither=Image.Dither.NONE)
        frames.append(q)
        durations.append(delay)

    # Final
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

"""
Staking Renderer - Real-time per-hit images
Renders individual frames for each hit in the fight
"""
import cv2
import io
import json
import os
from PIL import Image, ImageDraw, ImageFont

# Output size
OUTPUT_W = 480
OUTPUT_H = 270

# Default positions (overridden by staking_positions.json)
LEFT_CHAR_X = 168
RIGHT_CHAR_X = 312
HP_BAR_Y = 50
SPLAT_Y = 95
LABEL_Y = 32

# HP bar settings
HP_BAR_W = 70
HP_BAR_H = 8
HP_BAR_BORDER = 2

# Hitsplat display size
SPLAT_SIZE = 34

# Colors
HP_GREEN = (34, 177, 76)
HP_RED = (200, 30, 30)
HP_BORDER = (0, 0, 0)

VIDEO_PATH = 'assets/whip_fight.mp4'
FONT_PATH = 'assets/fonts/arialbd.ttf'
POSITIONS_PATH = 'staking_positions.json'

SPLAT_DAMAGE_PATH = 'assets/hitsplat_damage.png'
SPLAT_MAX_PATH = 'assets/hitsplat_max.png'
SPLAT_ZERO_PATH = 'assets/hitsplat_zero.png'

# Cached assets
_impact_frame = None
_idle_frame = None
_splat_damage = None
_splat_max = None
_splat_zero = None
_fonts = None


def _load_positions():
    global LEFT_CHAR_X, RIGHT_CHAR_X, HP_BAR_Y, SPLAT_Y, LABEL_Y
    if os.path.exists(POSITIONS_PATH):
        with open(POSITIONS_PATH, 'r') as f:
            pos = json.load(f)
        LEFT_CHAR_X = pos['left_hp_bar'][0]
        RIGHT_CHAR_X = pos['right_hp_bar'][0]
        HP_BAR_Y = pos['left_hp_bar'][1]
        SPLAT_Y = pos['left_hitsplat'][1]
        LABEL_Y = pos['left_label'][1]


def _load_assets():
    global _impact_frame, _idle_frame, _splat_damage, _splat_max, _splat_zero, _fonts
    if _impact_frame is not None:
        return

    _load_positions()

    # Load two key frames: idle (standing) and impact (whips hitting)
    cap = cv2.VideoCapture(VIDEO_PATH)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).resize((OUTPUT_W, OUTPUT_H), Image.LANCZOS)
        frames.append(img)
    cap.release()

    _idle_frame = frames[0]      # Standing pose
    _impact_frame = frames[17]   # Impact moment

    # Load hitsplat sprites
    def load_splat(path):
        img = Image.open(path).convert('RGBA')
        return img.resize((SPLAT_SIZE, SPLAT_SIZE), Image.LANCZOS)

    _splat_damage = load_splat(SPLAT_DAMAGE_PATH)
    _splat_max = load_splat(SPLAT_MAX_PATH)
    _splat_zero = load_splat(SPLAT_ZERO_PATH)

    # Load fonts
    try:
        _fonts = {
            'splat': ImageFont.truetype(FONT_PATH, 14),
            'hp': ImageFont.truetype(FONT_PATH, 10),
            'label': ImageFont.truetype(FONT_PATH, 11),
            'ko': ImageFont.truetype(FONT_PATH, 20),
        }
    except Exception:
        default = ImageFont.load_default()
        _fonts = {'splat': default, 'hp': default, 'label': default, 'ko': default}


def _draw_hp_bar(draw, x, y, current_hp, max_hp=99):
    bar_x = x - HP_BAR_W // 2
    bar_y = y - HP_BAR_H // 2
    draw.rectangle(
        [bar_x - HP_BAR_BORDER, bar_y - HP_BAR_BORDER,
         bar_x + HP_BAR_W + HP_BAR_BORDER, bar_y + HP_BAR_H + HP_BAR_BORDER],
        fill=HP_BORDER)
    draw.rectangle([bar_x, bar_y, bar_x + HP_BAR_W, bar_y + HP_BAR_H], fill=HP_RED)
    if current_hp > 0:
        green_w = int(HP_BAR_W * (current_hp / max_hp))
        if green_w > 0:
            draw.rectangle([bar_x, bar_y, bar_x + green_w, bar_y + HP_BAR_H], fill=HP_GREEN)


def _paste_hitsplat(frame, x, y, damage):
    if damage == 0:
        splat = _splat_zero.copy()
    elif damage >= 25:
        splat = _splat_max.copy()
    else:
        splat = _splat_damage.copy()

    splat_draw = ImageDraw.Draw(splat)
    text = str(damage)
    bbox = _fonts['splat'].getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = SPLAT_SIZE // 2 - tw // 2
    ty = SPLAT_SIZE // 2 - th // 2 - 1
    splat_draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0), font=_fonts['splat'])
    splat_draw.text((tx, ty), text, fill=(255, 255, 255), font=_fonts['splat'])
    frame.paste(splat, (x - SPLAT_SIZE // 2, y - SPLAT_SIZE // 2), splat)


def _draw_hp_text(draw, x, y, current_hp):
    text = str(current_hp)
    bbox = _fonts['hp'].getbbox(text)
    tw = bbox[2] - bbox[0]
    ty = y + HP_BAR_H // 2 + 3
    draw.text((x - tw // 2 + 1, ty + 1), text, fill=(0, 0, 0), font=_fonts['hp'])
    draw.text((x - tw // 2, ty), text, fill=(255, 255, 255), font=_fonts['hp'])


def _draw_label(draw, x, y, text, color):
    bbox = _fonts['label'].getbbox(text)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw // 2 + 1, y + 1), text, fill=(0, 0, 0), font=_fonts['label'])
    draw.text((x - tw // 2, y), text, fill=color, font=_fonts['label'])


def _base_frame(base, player_hp, host_hp):
    """Create a frame with HP bars and labels (no hitsplats)"""
    frame = base.copy().convert('RGBA')
    draw = ImageDraw.Draw(frame)
    _draw_label(draw, LEFT_CHAR_X, LABEL_Y, "YOU", _fonts['label'], (0, 255, 0))
    _draw_label(draw, RIGHT_CHAR_X, LABEL_Y, "HOST", _fonts['label'], (255, 60, 60))
    _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp)
    _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp)
    _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp)
    _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp)
    return frame


def render_idle_frame(player_hp, host_hp):
    """Render the idle/standing frame with current HP bars"""
    _load_assets()
    frame = _base_frame(_idle_frame, player_hp, host_hp)
    buf = io.BytesIO()
    frame.convert('RGB').save(buf, format='PNG')
    buf.seek(0)
    return buf


def render_hit_frame(player_hp, host_hp, player_hit, host_hit):
    """Render the impact frame with hitsplats showing the hits"""
    _load_assets()
    frame = _base_frame(_impact_frame, player_hp, host_hp)

    # Player's hit on host (right side)
    _paste_hitsplat(frame, RIGHT_CHAR_X, SPLAT_Y, player_hit)
    # Host's hit on player (left side)
    _paste_hitsplat(frame, LEFT_CHAR_X, SPLAT_Y, host_hit)

    buf = io.BytesIO()
    frame.convert('RGB').save(buf, format='PNG')
    buf.seek(0)
    return buf


def render_ko_frame(player_hp, host_hp, last_player_hit, last_host_hit):
    """Render the final KO frame"""
    _load_assets()
    frame = _base_frame(_impact_frame, player_hp, host_hp)

    # Last hitsplats
    if host_hp <= 0:
        _paste_hitsplat(frame, RIGHT_CHAR_X, SPLAT_Y, last_player_hit)
    if player_hp <= 0:
        _paste_hitsplat(frame, LEFT_CHAR_X, SPLAT_Y, last_host_hit)

    draw = ImageDraw.Draw(frame)

    # Winner text
    winner_text = "YOU WIN!" if host_hp <= 0 else "HOST WINS!"
    bbox = _fonts['ko'].getbbox(winner_text)
    tw = bbox[2] - bbox[0]
    wx = OUTPUT_W // 2 - tw // 2
    wy = 8
    draw.text((wx + 2, wy + 2), winner_text, fill=(0, 0, 0), font=_fonts['ko'])
    color = (0, 255, 0) if host_hp <= 0 else (255, 60, 60)
    draw.text((wx, wy), winner_text, fill=color, font=_fonts['ko'])

    buf = io.BytesIO()
    frame.convert('RGB').save(buf, format='PNG')
    buf.seek(0)
    return buf

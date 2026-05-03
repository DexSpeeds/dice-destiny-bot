"""
Staking Renderer - Overlays HP bars and real OSRS hitsplats on whip fight video
Creates animated GIF of the duel
Loads positions from staking_positions.json if available
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

# Hitsplat display size (scaled up from 24px originals)
SPLAT_SIZE = 34

# Colors
HP_GREEN = (34, 177, 76)
HP_RED = (200, 30, 30)
HP_BORDER = (0, 0, 0)

# Frames to sample per attack round (from 34 total)
# Frame 0-7: wind-up, 8-12: approach, 13-17: IMPACT, 18-22: recoil, 23-33: reset
#                windup   approach  IMPACT         recoil      reset
SAMPLE_FRAMES = [0,  4,    8,  11,  14, 16, 18,   22,  26,    31]
#  index:        0   1     2   3    4   5   6      7    8      9
# Hitsplats appear at index 4 (frame 14) through 7 (frame 22)
# HP updates at index 4 (impact moment)

VIDEO_PATH = 'assets/whip_fight.mp4'
FONT_PATH = 'assets/fonts/arialbd.ttf'
POSITIONS_PATH = 'staking_positions.json'

# Hitsplat sprite paths
SPLAT_DAMAGE_PATH = 'assets/hitsplat_damage.png'
SPLAT_MAX_PATH = 'assets/hitsplat_max.png'
SPLAT_ZERO_PATH = 'assets/hitsplat_zero.png'

# Preloaded assets
_video_frames = None
_splat_damage = None
_splat_max = None
_splat_zero = None


def _load_positions():
    """Load positions from JSON or use defaults"""
    global LEFT_CHAR_X, RIGHT_CHAR_X, HP_BAR_Y, SPLAT_Y, LABEL_Y

    if os.path.exists(POSITIONS_PATH):
        with open(POSITIONS_PATH, 'r') as f:
            pos = json.load(f)
        LEFT_CHAR_X = pos['left_hp_bar'][0]
        RIGHT_CHAR_X = pos['right_hp_bar'][0]
        HP_BAR_Y = pos['left_hp_bar'][1]
        SPLAT_Y = pos['left_hitsplat'][1]
        LABEL_Y = pos['left_label'][1]


def _load_hitsplats():
    """Load and scale hitsplat sprites"""
    global _splat_damage, _splat_max, _splat_zero

    if _splat_damage is not None:
        return

    def load_splat(path):
        img = Image.open(path).convert('RGBA')
        img = img.resize((SPLAT_SIZE, SPLAT_SIZE), Image.LANCZOS)
        return img

    _splat_damage = load_splat(SPLAT_DAMAGE_PATH)
    _splat_max = load_splat(SPLAT_MAX_PATH)
    _splat_zero = load_splat(SPLAT_ZERO_PATH)


def _load_video_frames():
    """Load and scale all frames from the whip fight video"""
    global _video_frames
    if _video_frames is not None:
        return _video_frames

    cap = cv2.VideoCapture(VIDEO_PATH)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img = img.resize((OUTPUT_W, OUTPUT_H), Image.LANCZOS)
        frames.append(img)
    cap.release()
    _video_frames = frames
    return frames


def _draw_hp_bar(draw, x, y, current_hp, max_hp=99):
    """Draw an OSRS-style HP bar"""
    bar_x = x - HP_BAR_W // 2
    bar_y = y - HP_BAR_H // 2

    # Black border
    draw.rectangle(
        [bar_x - HP_BAR_BORDER, bar_y - HP_BAR_BORDER,
         bar_x + HP_BAR_W + HP_BAR_BORDER, bar_y + HP_BAR_H + HP_BAR_BORDER],
        fill=HP_BORDER
    )

    # Red background (lost HP)
    draw.rectangle(
        [bar_x, bar_y, bar_x + HP_BAR_W, bar_y + HP_BAR_H],
        fill=HP_RED
    )

    # Green foreground (remaining HP)
    if current_hp > 0:
        green_w = int(HP_BAR_W * (current_hp / max_hp))
        if green_w > 0:
            draw.rectangle(
                [bar_x, bar_y, bar_x + green_w, bar_y + HP_BAR_H],
                fill=HP_GREEN
            )


def _paste_hitsplat(frame, x, y, damage, font):
    """Paste a real OSRS hitsplat sprite with damage number"""
    # Pick the right splat
    if damage == 0:
        splat = _splat_zero.copy()
    elif damage >= 25:  # Max hit
        splat = _splat_max.copy()
    else:
        splat = _splat_damage.copy()

    # Draw damage number on the splat
    splat_draw = ImageDraw.Draw(splat)
    text = str(damage)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = SPLAT_SIZE // 2 - tw // 2
    ty = SPLAT_SIZE // 2 - th // 2 - 1
    # Shadow
    splat_draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0), font=font)
    # White number
    splat_draw.text((tx, ty), text, fill=(255, 255, 255), font=font)

    # Paste onto frame using alpha mask
    paste_x = x - SPLAT_SIZE // 2
    paste_y = y - SPLAT_SIZE // 2
    frame.paste(splat, (paste_x, paste_y), splat)


def _draw_hp_text(draw, x, y, current_hp, font_small):
    """Draw HP number below the bar"""
    text = str(current_hp)
    bbox = font_small.getbbox(text)
    tw = bbox[2] - bbox[0]
    ty = y + HP_BAR_H // 2 + 3
    # Shadow then text
    draw.text((x - tw // 2 + 1, ty + 1), text, fill=(0, 0, 0), font=font_small)
    draw.text((x - tw // 2, ty), text, fill=(255, 255, 255), font=font_small)


def _draw_label(draw, x, y, text, font, color=(255, 255, 0)):
    """Draw a label (YOU / HOST) above HP bar"""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw // 2 + 1, y + 1), text, fill=(0, 0, 0), font=font)
    draw.text((x - tw // 2, y), text, fill=color, font=font)


def render_staking_gif(rounds):
    """
    Render the staking fight as an animated GIF

    Args:
        rounds: list of round dicts from Staking.play()

    Returns:
        BytesIO with the GIF data
    """
    _load_positions()
    _load_hitsplats()
    video_frames = _load_video_frames()

    if not video_frames:
        raise FileNotFoundError(f"Could not load video from {VIDEO_PATH}")

    total_video_frames = len(video_frames)

    try:
        font_splat = ImageFont.truetype(FONT_PATH, 14)
        font_hp = ImageFont.truetype(FONT_PATH, 10)
        font_label = ImageFont.truetype(FONT_PATH, 11)
    except Exception:
        font_splat = ImageFont.load_default()
        font_hp = font_splat
        font_label = font_splat

    gif_frames = []

    player_hp = 99
    host_hp = 99

    # Intro frames - show both at full HP, no splats
    for fi in [0, 8]:
        frame = video_frames[fi % total_video_frames].copy().convert('RGBA')
        draw = ImageDraw.Draw(frame)

        _draw_label(draw, LEFT_CHAR_X, LABEL_Y, "YOU", font_label, (0, 255, 0))
        _draw_label(draw, RIGHT_CHAR_X, LABEL_Y, "HOST", font_label, (255, 60, 60))
        _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp)
        _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp)
        _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp, font_hp)
        _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp, font_hp)

        gif_frames.append(frame.convert('RGB'))

    # Fight rounds
    for rnd_idx, rnd in enumerate(rounds):
        prev_player_hp = player_hp
        prev_host_hp = host_hp

        player_hit = rnd['player_hit']  # Player hits host
        host_hit = rnd['host_hit']      # Host hits player
        player_hp = rnd['player_hp']
        host_hp = rnd['host_hp']

        # === IDLE PHASE: standing still, waiting for next attack tick ===
        # Use frames 0-4 (standing pose) with longer durations
        # Skip idle on first round (intro covers it)
        if rnd_idx > 0:
            for fi in [0, 2, 4]:
                frame = video_frames[fi % total_video_frames].copy().convert('RGBA')
                draw = ImageDraw.Draw(frame)
                _draw_label(draw, LEFT_CHAR_X, LABEL_Y, "YOU", font_label, (0, 255, 0))
                _draw_label(draw, RIGHT_CHAR_X, LABEL_Y, "HOST", font_label, (255, 60, 60))
                _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, prev_player_hp)
                _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, prev_host_hp)
                _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, prev_player_hp, font_hp)
                _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, prev_host_hp, font_hp)
                gif_frames.append(frame.convert('RGB'))

        # === ATTACK PHASE: wind up -> impact -> recoil ===
        for i, fi in enumerate(SAMPLE_FRAMES):
            frame = video_frames[fi % total_video_frames].copy().convert('RGBA')
            draw = ImageDraw.Draw(frame)

            # Labels always visible
            _draw_label(draw, LEFT_CHAR_X, LABEL_Y, "YOU", font_label, (0, 255, 0))
            _draw_label(draw, RIGHT_CHAR_X, LABEL_Y, "HOST", font_label, (255, 60, 60))

            # HP bars: before impact show old HP, after impact show new HP
            if i < 4:
                _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, prev_player_hp)
                _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, prev_host_hp)
                _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, prev_player_hp, font_hp)
                _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, prev_host_hp, font_hp)
            else:
                _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp)
                _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp)
                _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp, font_hp)
                _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp, font_hp)

            # Hitsplats appear at impact (index 4) and stay visible through recoil (index 7)
            if 4 <= i <= 7:
                _paste_hitsplat(frame, RIGHT_CHAR_X, SPLAT_Y, player_hit, font_splat)
                if host_hit > 0 or prev_host_hp > 0:
                    _paste_hitsplat(frame, LEFT_CHAR_X, SPLAT_Y, host_hit, font_splat)

            gif_frames.append(frame.convert('RGB'))

    # Final frame - KO
    final_frame = video_frames[17 % total_video_frames].copy().convert('RGBA')
    draw = ImageDraw.Draw(final_frame)

    _draw_label(draw, LEFT_CHAR_X, LABEL_Y, "YOU", font_label, (0, 255, 0))
    _draw_label(draw, RIGHT_CHAR_X, LABEL_Y, "HOST", font_label, (255, 60, 60))
    _draw_hp_bar(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp)
    _draw_hp_bar(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp)
    _draw_hp_text(draw, LEFT_CHAR_X, HP_BAR_Y, player_hp, font_hp)
    _draw_hp_text(draw, RIGHT_CHAR_X, HP_BAR_Y, host_hp, font_hp)

    # KO splat on the loser
    if host_hp <= 0:
        _paste_hitsplat(final_frame, RIGHT_CHAR_X, SPLAT_Y, player_hit, font_splat)
    else:
        _paste_hitsplat(final_frame, LEFT_CHAR_X, SPLAT_Y, host_hit, font_splat)

    # Winner text at top center
    try:
        font_win = ImageFont.truetype(FONT_PATH, 18)
    except Exception:
        font_win = font_label

    winner_text = "YOU WIN!" if host_hp <= 0 else "HOST WINS!"
    bbox = font_win.getbbox(winner_text)
    tw = bbox[2] - bbox[0]
    wx = OUTPUT_W // 2 - tw // 2
    wy = 8
    draw.text((wx + 2, wy + 2), winner_text, fill=(0, 0, 0), font=font_win)
    win_color = (0, 255, 0) if host_hp <= 0 else (255, 60, 60)
    draw.text((wx, wy), winner_text, fill=win_color, font=font_win)

    final_rgb = final_frame.convert('RGB')
    for _ in range(5):
        gif_frames.append(final_rgb.copy())

    # Build GIF with shared palette
    palette_img = gif_frames[-1].quantize(colors=256, method=Image.Quantize.MEDIANCUT)

    quantized_frames = []
    for f in gif_frames:
        qf = f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, palette=palette_img)
        quantized_frames.append(qf)

    # Frame durations
    durations = []
    # Intro: 2 frames
    durations.extend([500, 400])
    # Fight rounds
    for rnd_idx, rnd in enumerate(rounds):
        # Idle phase (3 frames, skipped on first round)
        if rnd_idx > 0:
            durations.extend([250, 250, 250])  # ~750ms standing still between hits
        # Attack phase (10 frames)
        #              windup    approach   IMPACT+splats          recoil       reset
        durations.extend([60, 60,  70, 80,  150, 130, 100, 80,   60, 60])
    # Final hold
    durations.extend([1000] * 5)

    buf = io.BytesIO()
    quantized_frames[0].save(
        buf,
        format='GIF',
        save_all=True,
        append_images=quantized_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )
    buf.seek(0)
    return buf

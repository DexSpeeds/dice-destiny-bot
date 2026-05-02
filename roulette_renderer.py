"""
Roulette Renderer - D&D disk in frame, chips on table, text fields
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io
import math

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
TABLE_PATH = os.path.join(ASSETS_DIR, 'roulette_table.png')
DISK_PATH = os.path.join(ASSETS_DIR, 'roulette_disk.png')

WHEEL_CX, WHEEL_CY = 833, 264
WHEEL_RADIUS = 175

WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]
NUM_SLOTS = len(WHEEL_ORDER)
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]

# Chip positions on the betting table per bet type
# Measured from the table image
# Chip positions - from chip_position_tool
CHIP_POSITIONS = {
    'red': (770, 819),
    'black': (947, 817),
    'even': (572, 816),
    'odd': (1142, 819),
    'low': (394, 817),
    'high': (1313, 819),
    'dozen1': (495, 747),
    'dozen2': (856, 746),
    'dozen3': (1218, 746),
}

# Number cell positions on the table for specific number bets
# Row 3 (top): 3,6,9,12,15,18,21,24,27,30,33,36
# Row 2 (mid): 2,5,8,11,14,17,20,23,26,29,32,35
# Row 1 (bot): 1,4,7,10,13,16,19,22,25,28,31,34
TABLE_X_START = 445
TABLE_CELL_W = 73
TABLE_ROW_Y = {1: 668, 2: 592, 3: 518}
ZERO_POS = (395, 592)

# Number cell positions on the table grid (approximate centers)
# Row 1 (top): 3,6,9,12,15,18,21,24,27,30,33,36
# Row 2 (mid): 2,5,8,11,14,17,20,23,26,29,32,35
# Row 3 (bot): 1,4,7,10,13,16,19,22,25,28,31,34
# Each cell is roughly 73px wide, starting at X~410
TABLE_START_X = 410
TABLE_ROW_Y = {3: 530, 2: 610, 1: 690}  # Row for number%3
TABLE_CELL_W = 73
ZERO_POS = (380, 610)  # 0 position

_font_cache = {}
_table_bg = None
_disk_img = None


def _get_font(size):
    if size not in _font_cache:
        for p in ["assets/fonts/georgiab.ttf", "assets/fonts/arialbd.ttf"]:
            try:
                _font_cache[size] = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def _get_table():
    global _table_bg
    if _table_bg is None:
        _table_bg = Image.open(TABLE_PATH).convert('RGBA')
    return _table_bg.copy()


def _get_disk():
    global _disk_img
    if _disk_img is None:
        _disk_img = Image.open(DISK_PATH).convert('RGBA')
    return _disk_img


def _number_color(n):
    if n == 0: return 'green'
    return 'red' if n in RED_NUMBERS else 'black'


def _paste_disk(table, rotation, ball_number=None):
    disk = _get_disk().copy()

    # Draw ball on the disk BEFORE rotating - from ball_position_tool config
    # Ball radius=414, zero_angle=-90.3 on 1254x1254 disk
    if ball_number is not None:
        idx = WHEEL_ORDER.index(ball_number) if ball_number in WHEEL_ORDER else 0
        slot_angle = 2 * math.pi / NUM_SLOTS

        disk_cx = disk.width // 2   # 627
        disk_cy = disk.height // 2  # 627
        ball_r = 414  # From tool
        zero_angle = math.radians(-90.3)  # From tool

        angle = zero_angle + idx * slot_angle
        bx = int(disk_cx + ball_r * math.cos(angle))
        by = int(disk_cy + ball_r * math.sin(angle))

        d = ImageDraw.Draw(disk)
        # Glow
        d.ellipse([(bx - 20, by - 20), (bx + 20, by + 20)], fill=(255, 255, 200, 120))
        # Ball
        d.ellipse([(bx - 14, by - 14), (bx + 14, by + 14)], fill=(255, 255, 255), outline=(255, 215, 0), width=3)
        # Shine
        d.ellipse([(bx - 6, by - 6), (bx + 6, by + 6)], fill=(255, 255, 255))

    rotated = disk.rotate(-rotation, resample=Image.BICUBIC, expand=False)
    size = WHEEL_RADIUS * 2
    rotated = rotated.resize((size, size), Image.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([(0, 0), (size, size)], fill=255)
    table.paste(rotated, (WHEEL_CX - WHEEL_RADIUS, WHEEL_CY - WHEEL_RADIUS), mask)


def _draw_rolling_ball(draw, angle_degrees):
    """Draw ball rolling around the rim of the wheel at a given angle"""
    angle_rad = math.radians(angle_degrees - 90)
    # Ball rolls on the outer rim, just inside the frame
    rim_r = WHEEL_RADIUS - 8
    bx = WHEEL_CX + rim_r * math.cos(angle_rad)
    by = WHEEL_CY + rim_r * math.sin(angle_rad)

    # Glow
    draw.ellipse([(bx - 12, by - 12), (bx + 12, by + 12)], fill=(255, 255, 200, 120))
    # Ball
    draw.ellipse([(bx - 8, by - 8), (bx + 8, by + 8)], fill=(255, 255, 255), outline=(255, 215, 0), width=2)
    # Shine
    draw.ellipse([(bx - 4, by - 4), (bx + 4, by + 4)], fill=(255, 255, 255))


def _get_number_pos(number):
    """Get position of a specific number on the table grid"""
    if number == 0:
        return ZERO_POS
    col = (number - 1) // 3
    row = number % 3
    if row == 0:
        row = 3
    x = TABLE_X_START + col * TABLE_CELL_W + TABLE_CELL_W // 2
    y = TABLE_ROW_Y.get(row, 592)
    return (x, y)


def _draw_chip(draw, bet_type, amount):
    """Draw a chip on the betting area"""
    # Check if betting on a specific number
    if bet_type.startswith('number_'):
        num = int(bet_type.split('_')[1])
        pos = _get_number_pos(num)
    else:
        pos = CHIP_POSITIONS.get(bet_type)
    if not pos:
        return
    cx, cy = pos
    chip_r = 25

    # Outer ring
    draw.ellipse([(cx - chip_r, cy - chip_r), (cx + chip_r, cy + chip_r)],
                 fill=(160, 30, 30), outline=(255, 215, 0), width=4)
    # Inner ring
    draw.ellipse([(cx - chip_r + 6, cy - chip_r + 6), (cx + chip_r - 6, cy + chip_r - 6)],
                 outline=(255, 215, 0, 180), width=2)

    # Amount text
    font = _get_font(16)
    if amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        text = f"{amount // 1_000_000}M"
    elif amount >= 1_000:
        text = f"{amount // 1_000}K"
    else:
        text = str(amount)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text, fill=(255, 255, 255), font=font)


def _highlight_winning_number(draw, number):
    """Highlight the winning number cell on the table"""
    if number == 0:
        x, y = ZERO_POS
    else:
        col = (number - 1) // 3  # 0-11
        row = number % 3  # 1, 2, or 0(=3rd row)
        if row == 0:
            row = 3
        x = TABLE_START_X + col * TABLE_CELL_W + TABLE_CELL_W // 2
        y = TABLE_ROW_Y.get(row, 610)

    # Glow effect around the number
    draw.ellipse([(x - 25, y - 25), (x + 25, y + 25)],
                 outline=(255, 215, 0), width=3)


def _fill_fields(draw, game_id, bettor, chip, payout,
                 winning_number, color, result_text, total_win,
                 recent_results, streak, biggest, wagered):
    """Fill text fields - positions measured from zoomed crops"""
    font = _get_font(20)
    gold = (220, 190, 100)
    white = (255, 255, 255)
    green = (100, 255, 100)
    red = (255, 100, 100)

    # GAME INFO (left panel) - positions from position_tool
    draw.text((352, 137), str(game_id), fill=gold, font=font)
    draw.text((357, 188), str(bettor), fill=gold, font=font)
    draw.text((321, 231), str(chip), fill=gold, font=font)
    draw.text((347, 276), str(payout), fill=gold, font=font)

    # RESULT (right panel) - positions from position_tool
    nc = red if color == 'red' else (white if color == 'black' else green)
    draw.text((1324, 137), str(winning_number), fill=nc, font=font)
    draw.text((1221, 182), color.upper() if color else "", fill=nc, font=font)
    rc = green if result_text == 'WIN' else red
    draw.text((1232, 223), result_text, fill=rc, font=font)
    draw.text((1255, 261), str(total_win), fill=gold, font=font)

    # STATS - positions from position_tool
    draw.text((1212, 367), str(streak), fill=gold, font=font)
    draw.text((1256, 400), str(biggest), fill=gold, font=font)
    draw.text((1280, 431), str(wagered), fill=gold, font=font)

    # RECENT RESULTS - position from position_tool
    small = _get_font(17)
    x = 305
    if recent_results:
        for num in recent_results[:8]:
            if isinstance(num, int):
                c = _number_color(num)
                tc = red if c == 'red' else (green if c == 'green' else (200, 200, 200))
                draw.text((x, 398), str(num), fill=tc, font=small)
                x += 38


def render_roulette_gif(game_id, bettor, chip, bet_type, winning_number,
                        won, payout, recent_results=None,
                        streak=0, biggest_win=0, total_wagered=0):
    """Animated roulette with spinning disk, chip on bet, ball landing"""
    color = _number_color(winning_number)
    result_text = "WIN" if won else "LOSS"
    total_win = f"{payout:,} GP" if won else "0 GP"

    win_idx = WHEEL_ORDER.index(winning_number) if winning_number in WHEEL_ORDER else 0
    # Rotate so winning number ends up at the TOP (where ball is)
    # The disk has numbers arranged clockwise, 0 at top
    # We need to rotate -(win_idx * slot_angle) to bring it to top
    # Plus 3 full spins for animation
    slot_angle = 360 / NUM_SLOTS
    final_rotation = 360 * 3 - win_idx * slot_angle

    frames = []
    durations = []

    # Ball spins opposite direction, faster than disk, then slows and drops in
    # Total ball travel: ~5 full rotations counter-clockwise
    ball_total_rotation = -360 * 5

    # Build final frame first to get palette
    final_img = _get_table()
    _paste_disk(final_img, final_rotation, ball_number=winning_number)
    final_draw = ImageDraw.Draw(final_img)
    _draw_chip(final_draw, bet_type, chip)
    _highlight_winning_number(final_draw, winning_number)
    _fill_fields(final_draw, f"#{game_id}", bettor, f"{chip:,} GP",
                 f"{payout:,} GP" if won else "0 GP",
                 winning_number, color, result_text, total_win,
                 recent_results or [], streak,
                 f"{biggest_win:,}" if biggest_win else "0",
                 f"{total_wagered:,}" if total_wagered else "0")
    final_rgb = final_img.convert('RGB')
    palette_img = final_rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)

    # Ball does 2 smooth clockwise laps around the rim, then lands
    # 12 frames for 2 full laps (each frame = 60 degrees)
    for i in range(12):
        ball_angle = (i / 12) * 720  # 2 full laps clockwise
        rot = (i / 12) * final_rotation * 0.6  # disk spins slower

        img = _get_table()
        _paste_disk(img, rot)
        d = ImageDraw.Draw(img)
        _draw_rolling_ball(d, ball_angle)
        _draw_chip(d, bet_type, chip)
        _fill_fields(d, f"#{game_id}", bettor, f"{chip:,} GP", "...",
                     "?", "", "SPINNING...", "...",
                     recent_results or [], "", "", "")
        rgb = img.convert('RGB')
        frames.append(rgb.quantize(palette=palette_img, dither=Image.Dither.NONE))
        durations.append(70)

    # Slowing down - 3 frames, disk approaches final position
    for i, delay in enumerate([200, 400, 700]):
        progress = 0.6 + ((i + 1) / 3) * 0.4
        rot = final_rotation * progress

        img = _get_table()
        _paste_disk(img, rot)
        d = ImageDraw.Draw(img)
        # Ball slows and stays near top (where it'll land)
        ball_angle = 720 + (i + 1) * 30
        _draw_rolling_ball(d, ball_angle)
        _draw_chip(d, bet_type, chip)
        _fill_fields(d, f"#{game_id}", bettor, f"{chip:,} GP", "...",
                     "?", "", "SPINNING...", "...",
                     recent_results or [], "", "", "")
        rgb = img.convert('RGB')
        frames.append(rgb.quantize(palette=palette_img, dither=Image.Dither.NONE))
        durations.append(delay)

    # Phase 3: Final result (hold 3s)
    frames.append(palette_img)
    durations.append(3000)

    buf = io.BytesIO()
    frames[0].save(buf, format='GIF', save_all=True,
                   append_images=frames[1:],
                   duration=durations, loop=0, optimize=False)
    buf.seek(0)
    return buf

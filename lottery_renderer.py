"""
Lottery Renderers:
1. Ticket - individual DM ticket with numbers
2. Background - active lottery embed with player list
3. Winners - podium with top 3 after draw
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io
import random
from datetime import datetime

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
TICKET_PATH = os.path.join(ASSETS_DIR, 'lottery_ticket.png')
BG_PATH = os.path.join(ASSETS_DIR, 'Lottery background.png')
WINNERS_PATH = os.path.join(ASSETS_DIR, 'Lottery winners.png')

NUM_BOXES = 10
PLAYER_LINE_HEIGHT = 35  # Pixels between each player name

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


def generate_lottery_numbers():
    return [random.randint(1, 99) for _ in range(NUM_BOXES)]


# ==================== TICKET ====================

def render_ticket(player_name, ticket_number, numbers, date_str=None):
    """Render individual lottery ticket as PNG."""
    img = Image.open(TICKET_PATH).convert('RGB')
    draw = ImageDraw.Draw(img)

    field_font = _get_font(38)
    number_font = _get_font(42)
    small_font = _get_font(30)

    if date_str is None:
        date_str = datetime.now().strftime("%d/%m/%Y")

    ink = (40, 25, 15)
    num_ink = (50, 20, 60)

    draw.text((310, 480), player_name, fill=ink, font=field_font)
    draw.text((1100, 480), f"#{ticket_number}", fill=ink, font=field_font)
    draw.text((340, 775), date_str, fill=ink, font=small_font)

    BOX_CENTERS = [252, 369, 486, 601, 715, 828, 942, 1062, 1185, 1305]
    num_y = 685
    for i, num in enumerate(numbers[:NUM_BOXES]):
        draw.text((BOX_CENTERS[i], num_y), str(num), fill=num_ink, font=number_font, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


# ==================== LOTTERY BACKGROUND ====================

def render_lottery_background(total_pot, time_left, total_entries):
    """Render lottery background with big readable text - pot, timer, entries."""
    img = Image.open(BG_PATH).convert('RGB')
    draw = ImageDraw.Draw(img)

    big_font = _get_font(52)
    title_font = _get_font(40)
    info_font = _get_font(34)

    gold = (220, 190, 100)
    white = (255, 255, 255)

    # Big centered text
    w = img.width
    draw.text((w // 2, 180), "DICE & DESTINY", fill=gold, font=title_font, anchor="mm")
    draw.text((w // 2, 230), "LOTTERY", fill=gold, font=big_font, anchor="mm")

    draw.text((w // 2, 360), total_pot, fill=white, font=big_font, anchor="mm")
    draw.text((w // 2, 440), time_left, fill=gold, font=info_font, anchor="mm")
    draw.text((w // 2, 500), total_entries, fill=gold, font=info_font, anchor="mm")

    # Ticket price at bottom
    draw.text((w // 2, 580), "Ticket: 10,000,000 GP", fill=(180, 160, 120), font=info_font, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


# ==================== WINNERS PODIUM ====================

def render_lottery_winners(winners):
    """
    Render the lottery winners podium.

    Args:
        winners: list of {'user_name': str, 'prize': int, 'place': int}
    """
    img = Image.open(WINNERS_PATH).convert('RGB')
    draw = ImageDraw.Draw(img)

    name_font = _get_font(28)
    prize_font = _get_font(22)
    gold = (220, 190, 100)
    white = (255, 255, 255)

    # Positions from position tool
    positions = {
        1: {'name': (599, 909), 'prize': (543, 929)},
        2: {'name': (221, 909), 'prize': (174, 937)},
        3: {'name': (955, 914), 'prize': (902, 942)},
    }

    for w in winners[:3]:
        place = w['place']
        pos = positions.get(place)
        if not pos:
            continue

        name = w['user_name'][:15]
        prize = f"{w['prize']:,} GP"

        # Center the text horizontally around the position
        draw.text(pos['name'], name, fill=white, font=name_font, anchor="mm")
        draw.text(pos['prize'], prize, fill=gold, font=prize_font, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

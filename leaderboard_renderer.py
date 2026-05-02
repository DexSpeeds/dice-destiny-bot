"""
Leaderboard Renderer - Top 10 wagered on the D&D leaderboard image
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io
import json

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
LB_PATH = os.path.join(ASSETS_DIR, 'LeaderBoard1.png')
POS_PATH = os.path.join(os.path.dirname(__file__), 'leaderboard_positions.json')

_font_cache = {}


def _get_font(size):
    if size not in _font_cache:
        for p in ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
            try:
                _font_cache[size] = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def render_leaderboard(players):
    """
    Render the leaderboard image with top 10 players.

    Args:
        players: list of {'name': str, 'wagered': int} sorted by wagered desc
    """
    img = Image.open(LB_PATH).convert('RGB')
    draw = ImageDraw.Draw(img)

    with open(POS_PATH, 'r') as f:
        positions = json.load(f)

    name_font = _get_font(28)
    amount_font = _get_font(24)

    white = (255, 255, 255)
    gold = (220, 190, 100)

    for i in range(min(10, len(players))):
        row = i + 1
        name_key = f"ROW{row}_NAME"
        amount_key = f"ROW{row}_AMOUNT"

        if name_key not in positions or amount_key not in positions:
            continue

        name_pos = positions[name_key]
        amount_pos = positions[amount_key]

        name = players[i]['name'][:15]
        wagered = players[i]['wagered']

        if wagered >= 1_000_000_000:
            amount_text = f"{wagered / 1_000_000_000:.1f}B GP"
        elif wagered >= 1_000_000:
            amount_text = f"{wagered / 1_000_000:.1f}M GP"
        elif wagered >= 1_000:
            amount_text = f"{wagered / 1_000:.0f}K GP"
        else:
            amount_text = f"{wagered:,} GP"

        draw.text((name_pos['x'], name_pos['y']), name, fill=white, font=name_font)
        draw.text((amount_pos['x'], amount_pos['y']), amount_text, fill=gold, font=amount_font)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

"""
Rates System - Scrapes OSRS gold prices from eldorado.gg
Renders prices on the D&D rates image
Posts to channel and auto-updates
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io
import json
import aiohttp
import time
import re

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
RATES_PATH = os.path.join(ASSETS_DIR, 'rates.png')
POS_PATH = os.path.join(os.path.dirname(__file__), 'rates_positions.json')
FONT_PATH = os.path.join(ASSETS_DIR, 'fonts', 'georgiab.ttf')

_font_cache = {}


def _get_font(size):
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype(FONT_PATH, size)
        except OSError:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


async def fetch_osrs_price():
    """Scrape OSRS gold price from eldorado.gg"""
    url = "https://www.eldorado.gg/osrs-gold/g/10-0-0"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

                # Try to find price in the HTML
                # Look for patterns like "$0.38" or "0.38" near "per M" or "million"
                prices = re.findall(r'\$?(0\.\d{2,3})', html)
                if prices:
                    # Usually the first price is the sell/buy price
                    return float(prices[0])
    except Exception as e:
        print(f"Price fetch error: {e}")
    return None


def calculate_rates(base_price):
    """Calculate buy/sell rates from base price with markup"""
    if not base_price:
        base_price = 0.38  # Fallback

    return {
        'buy_crypto': round(base_price * 1.05, 2),   # 5% markup for crypto
        'buy_other': round(base_price * 1.15, 2),     # 15% markup for other methods
        'sell': round(base_price * 0.85, 2),           # 15% below for selling
    }


def render_rates(buy_crypto, buy_other, sell_price):
    """Render prices on the rates template"""
    img = Image.open(RATES_PATH).convert('RGB')
    draw = ImageDraw.Draw(img)

    with open(POS_PATH, 'r') as f:
        positions = json.load(f)

    price_font = _get_font(36)
    gold = (220, 190, 100)
    white = (255, 255, 255)

    # Buy Crypto price
    pos = positions.get('BUY_CRYPTO_PRICE', {})
    if pos:
        draw.text((pos['x'], pos['y']), f"${buy_crypto:.2f}/M", fill=gold, font=price_font, anchor="mm")

    # Buy Other price
    pos = positions.get('BUY_OTHER_PRICE', {})
    if pos:
        draw.text((pos['x'], pos['y']), f"${buy_other:.2f}/M", fill=gold, font=price_font, anchor="mm")

    # Sell price
    pos = positions.get('SELL_PRICE', {})
    if pos:
        draw.text((pos['x'], pos['y']), f"${sell_price:.2f}/M", fill=white, font=price_font, anchor="mm")

    # Updated timestamp at bottom
    update_font = _get_font(20)
    draw.text((img.width // 2, img.height - 40),
              f"Updated: {time.strftime('%H:%M UTC', time.gmtime())}",
              fill=(150, 140, 120), font=update_font, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

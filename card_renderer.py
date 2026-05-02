"""
Card Renderer - Cuts individual cards from sprite sheets
and renders blackjack hands as images
"""
from PIL import Image, ImageDraw, ImageFont
import os
import io

CARDS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'cards', 'individual')
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
DARK_BG = (47, 49, 54)

CARD_ORDER = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
SUIT_NAMES = {'♠': 'Spades', '♥': 'Hearts', '♦': 'Diamonds', '♣': 'Clubs'}

# Card cache
_card_cache = {}
_facedown = None
TARGET_W, TARGET_H = 249, 357


def _cut_cards():
    """Load individual card images from files"""
    global _facedown

    for suit_sym, suit_name in SUIT_NAMES.items():
        for rank in CARD_ORDER:
            path = os.path.join(CARDS_DIR, f'{suit_name}_{rank}.png')
            if os.path.exists(path):
                card = Image.open(path).convert('RGBA')
                card = card.resize((TARGET_W, TARGET_H), Image.LANCZOS)
                _card_cache[(rank, suit_sym)] = card

    # Face down card
    fd_path = os.path.join(CARDS_DIR, 'facedown.png')
    if not os.path.exists(fd_path):
        fd_path = os.path.join(ASSETS_DIR, 'faced down card.png')
    if os.path.exists(fd_path):
        sheet = Image.open(fd_path).convert('RGBA')
        sw, sh = sheet.size
        # If it's a sprite sheet (2x2), take top-left
        if sw > 400:
            sheet = sheet.crop((0, 0, sw // 2, sh // 2))
        _facedown = sheet.resize((TARGET_W, TARGET_H), Image.LANCZOS)


def get_card_image(rank, suit):
    """Get a single card image"""
    if not _card_cache:
        _cut_cards()
    return _card_cache.get((rank, suit))


def get_facedown():
    """Get the face-down card image"""
    if _facedown is None:
        _cut_cards()
    return _facedown


TABLE_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'blackjack_table.png')
_table_bg = None


def _get_table():
    global _table_bg
    if _table_bg is None:
        _table_bg = Image.open(TABLE_PATH).convert('RGBA')
    return _table_bg.copy()


def render_blackjack_hand(player_cards, dealer_cards, hide_dealer=True, result=None, split_cards=None, split_result=None, active_hand='main'):
    """
    Render blackjack on the Chase table background.
    Dealer cards top area, player cards bottom area.
    """
    if not _card_cache:
        _cut_cards()

    canvas = _get_table()
    table_w, table_h = canvas.size  # 1448 x 1086
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 48)
        big_font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
        big_font = font

    # Card size on the table
    cw, ch = 200, 286
    overlap = 130

    gold = (255, 215, 0)
    white = (255, 255, 255)
    green = (80, 255, 120)
    red = (255, 80, 80)

    # === DEALER CARDS (in front of the dealer, on the table) ===
    dealer_total_w = cw + (len(dealer_cards) - 1) * overlap if dealer_cards else 0
    dealer_start_x = (table_w - dealer_total_w) // 2
    dealer_y = 440

    for i, (rank, suit) in enumerate(dealer_cards):
        if hide_dealer and i == 1:
            card_img = get_facedown()
        else:
            card_img = get_card_image(rank, suit)

        if card_img:
            resized = card_img.resize((cw, ch), Image.LANCZOS)
            x = dealer_start_x + i * overlap
            canvas.paste(resized, (x, dealer_y), resized)

    # Dealer value
    if not hide_dealer:
        d_val = _calc_display_value(dealer_cards)
        val_x = dealer_start_x + dealer_total_w + 25
        val_y = dealer_y + ch // 2 - 24
        draw.text((val_x + 3, val_y + 3), str(d_val), fill=(0, 0, 0, 220), font=font)
        draw.text((val_x, val_y), str(d_val), fill=gold, font=font)

    # === PLAYER CARDS (bottom area) ===
    if split_cards:
        # Split: two hands side by side
        gap = 60
        hand1_w = cw + (len(player_cards) - 1) * overlap if player_cards else cw
        hand2_w = cw + (len(split_cards) - 1) * overlap if split_cards else cw
        total_w = hand1_w + gap + hand2_w
        start_x = (table_w - total_w) // 2
        player_y = 780

        # Hand 1 (left)
        for i, (rank, suit) in enumerate(player_cards):
            card_img = get_card_image(rank, suit)
            if card_img:
                resized = card_img.resize((cw, ch), Image.LANCZOS)
                canvas.paste(resized, (start_x + i * overlap, player_y), resized)

        p_val = _calc_display_value(player_cards)
        h1_label_x = start_x + hand1_w // 2
        label_color = gold if active_hand == 'main' else (150, 150, 150)
        draw.text((h1_label_x - 20 + 2, player_y - 35 + 2), str(p_val), fill=(0, 0, 0, 220), font=font)
        draw.text((h1_label_x - 20, player_y - 35), str(p_val), fill=label_color, font=font)
        if active_hand == 'main' and not result:
            draw.text((h1_label_x - 10, player_y - 70), "▼", fill=gold, font=font)

        # Hand 2 (right)
        hand2_x = start_x + hand1_w + gap
        for i, (rank, suit) in enumerate(split_cards):
            card_img = get_card_image(rank, suit)
            if card_img:
                resized = card_img.resize((cw, ch), Image.LANCZOS)
                canvas.paste(resized, (hand2_x + i * overlap, player_y), resized)

        s_val = _calc_display_value(split_cards)
        h2_label_x = hand2_x + hand2_w // 2
        label_color2 = gold if active_hand == 'split' else (150, 150, 150)
        draw.text((h2_label_x - 20 + 2, player_y - 35 + 2), str(s_val), fill=(0, 0, 0, 220), font=font)
        draw.text((h2_label_x - 20, player_y - 35), str(s_val), fill=label_color2, font=font)
        if active_hand == 'split' and not result:
            draw.text((h2_label_x - 10, player_y - 70), "▼", fill=gold, font=font)
    else:
        # Single hand - centered
        player_total_w = cw + (len(player_cards) - 1) * overlap if player_cards else 0
        player_start_x = (table_w - player_total_w) // 2
        player_y = 780

        for i, (rank, suit) in enumerate(player_cards):
            card_img = get_card_image(rank, suit)
            if card_img:
                resized = card_img.resize((cw, ch), Image.LANCZOS)
                x = player_start_x + i * overlap
                canvas.paste(resized, (x, player_y), resized)

        p_val = _calc_display_value(player_cards)
        val_x = player_start_x + player_total_w + 25
        val_y = player_y + ch // 2 - 24
        draw.text((val_x + 3, val_y + 3), str(p_val), fill=(0, 0, 0, 220), font=font)
        draw.text((val_x, val_y), str(p_val), fill=gold, font=font)

    # Result text
    if result:
        result_colors = {
            'win': green, 'blackjack': green,
            'loss': red, 'bust': red,
            'push': (150, 150, 150),
        }
        result_texts = {
            'win': 'YOU WIN!', 'blackjack': 'BLACKJACK!',
            'loss': 'DEALER WINS', 'bust': 'BUST!',
            'push': 'PUSH',
        }
        color = result_colors.get(result, white)
        text = result_texts.get(result, result.upper())
        bbox = draw.textbbox((0, 0), text, font=big_font)
        tw = bbox[2] - bbox[0]
        # Draw with shadow for readability
        cx = (table_w - tw) // 2
        cy = 720
        draw.text((cx + 3, cy + 3), text, fill=(0, 0, 0, 200), font=big_font)
        draw.text((cx, cy), text, fill=color, font=big_font)

    # Full resolution for Discord
    canvas = canvas.resize((1448, 1086), Image.LANCZOS)

    buf = io.BytesIO()
    canvas.save(buf, format='PNG')
    buf.seek(0)
    return buf


def _calc_display_value(cards):
    """Calculate hand value for display"""
    value = 0
    aces = 0
    for rank, suit in cards:
        if rank == 'A':
            value += 11
            aces += 1
        elif rank in ('J', 'Q', 'K'):
            value += 10
        else:
            value += int(rank)

    while value > 21 and aces > 0:
        value -= 10
        aces -= 1

    return value

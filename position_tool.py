"""
Generic Position Tool - Click to place text on any image.
Pass the image and field names as arguments.
Right-click or Z to undo. S to save.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import sys

# Config - change these for different images
CONFIGS = {
    'lottery_bg': {
        'image': 'assets/Lottery background.png',
        'output': 'lottery_bg_positions.json',
        'fields': ['TITLE', 'TICKET_PRICE', 'TOTAL_POT', 'TIME_LEFT', 'TOTAL_ENTRIES',
                   'PLAYER_LIST_START'],
        'preview': {'TITLE': 'DICE & DESTINY LOTTERY', 'TICKET_PRICE': 'Ticket: 10,000,000 GP',
                    'TOTAL_POT': 'Pot: 150,000,000 GP', 'TIME_LEFT': 'Draw in: 12h 30m',
                    'TOTAL_ENTRIES': '15 entries',
                    'PLAYER_LIST_START': 'Dex - 5 tickets | Lavas - 3 tickets'},
    },
    'lottery_winners': {
        'image': 'assets/Lottery winners.png',
        'output': 'lottery_winners_positions.json',
        'fields': ['WINNER_1ST_NAME', 'WINNER_1ST_PRIZE', 'WINNER_2ND_NAME', 'WINNER_2ND_PRIZE', 'WINNER_3RD_NAME', 'WINNER_3RD_PRIZE'],
        'preview': {'WINNER_1ST_NAME': 'Dex', 'WINNER_1ST_PRIZE': '67,500,000 GP',
                    'WINNER_2ND_NAME': 'Lavas', 'WINNER_2ND_PRIZE': '40,500,000 GP',
                    'WINNER_3RD_NAME': 'Chase', 'WINNER_3RD_PRIZE': '27,000,000 GP'},
    },
}

# Pick config
if len(sys.argv) > 1 and sys.argv[1] in CONFIGS:
    cfg = CONFIGS[sys.argv[1]]
else:
    print("Available configs:")
    for k in CONFIGS:
        print(f"  python position_tool.py {k}")
    print(f"\nDefaulting to: lottery_winners")
    cfg = CONFIGS['lottery_winners']

IMAGE_PATH = cfg['image']
OUTPUT_FILE = cfg['output']
FIELDS = cfg['fields']
PREVIEW = cfg['preview']

positions = {}
field_idx = 0


def render_preview():
    preview = base_img.copy()
    draw = ImageDraw.Draw(preview)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 24)
    except:
        font = ImageFont.load_default()

    gold = (220, 190, 100)
    for field, pos in positions.items():
        text = PREVIEW.get(field, field)
        draw.text((pos['x'], pos['y']), text, fill=gold, font=font)
        draw.ellipse([(pos['x']-3, pos['y']-3), (pos['x']+3, pos['y']+3)], fill=(255, 0, 0))

    return ImageTk.PhotoImage(preview.resize((display_w, display_h), Image.LANCZOS))


def update_canvas():
    global photo
    photo = render_preview()
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=photo)


def on_click(event):
    global field_idx
    if field_idx >= len(FIELDS):
        return
    x = int(event.x * scale_x)
    y = int(event.y * scale_y)
    positions[FIELDS[field_idx]] = {"x": x, "y": y}
    print(f"  {FIELDS[field_idx]}: ({x}, {y})")
    update_canvas()
    field_idx += 1
    if field_idx < len(FIELDS):
        label_var.set(f"Click on: {FIELDS[field_idx]}  |  Right-click/Z = undo | S = save")
    else:
        label_var.set("All done! Press S to save.")


def undo(event=None):
    global field_idx
    if field_idx <= 0:
        return
    field_idx -= 1
    if FIELDS[field_idx] in positions:
        del positions[FIELDS[field_idx]]
    update_canvas()
    label_var.set(f"Click on: {FIELDS[field_idx]}  |  Right-click/Z = undo | S = save")


def save(event=None):
    if positions:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(positions, f, indent=2)
        print(f"\nSaved to {OUTPUT_FILE}")
        label_var.set(f"SAVED! ({len(positions)} positions)")


base_img = Image.open(IMAGE_PATH).convert("RGBA")
orig_w, orig_h = base_img.size

root = tk.Tk()
root.title(f"Position Tool - {OUTPUT_FILE}")

screen_h = min(root.winfo_screenheight() - 150, 850)
scale = screen_h / orig_h
display_w = int(orig_w * scale)
display_h = int(orig_h * scale)
scale_x = orig_w / display_w
scale_y = orig_h / display_h

photo = render_preview()

label_var = tk.StringVar(value=f"Click on: {FIELDS[0]}  |  Right-click/Z = undo | S = save")
tk.Label(root, textvariable=label_var, font=("Arial", 14, "bold"), fg="white", bg="black").pack(fill="x")

canvas = tk.Canvas(root, width=display_w, height=display_h)
canvas.pack()
canvas.create_image(0, 0, anchor="nw", image=photo)
canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-3>", undo)
root.bind("z", undo)
root.bind("s", save)

root.mainloop()

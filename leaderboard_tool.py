"""
Leaderboard Position Tool - Click each row's name and amount position
20 clicks total: Row 1 name, Row 1 amount, Row 2 name, Row 2 amount, etc.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json

IMAGE_PATH = "assets/LeaderBoard1.png"
OUTPUT_FILE = "leaderboard_positions.json"

FIELDS = []
for i in range(1, 11):
    FIELDS.append(f"ROW{i}_NAME")
    FIELDS.append(f"ROW{i}_AMOUNT")

PREVIEW_NAMES = ["Dex", "Lavas", "Chase", "Ajax", "Savior", "Dicer", "KDanger", "Danny", "Biggus", "Lisa"]
PREVIEW_AMOUNTS = ["150M GP", "80M GP", "45M GP", "30M GP", "25M GP", "20M GP", "15M GP", "10M GP", "5M GP", "1M GP"]

positions = {}
field_idx = 0


def render_preview():
    preview = base_img.copy()
    draw = ImageDraw.Draw(preview)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 22)
    except:
        font = ImageFont.load_default()

    gold = (220, 190, 100)
    white = (255, 255, 255)

    for field, pos in positions.items():
        row_num = int(field.split("ROW")[1].split("_")[0]) - 1
        if "NAME" in field:
            draw.text((pos['x'], pos['y']), PREVIEW_NAMES[row_num], fill=white, font=font)
        else:
            draw.text((pos['x'], pos['y']), PREVIEW_AMOUNTS[row_num], fill=gold, font=font)
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

    row = FIELDS[field_idx].split("ROW")[1].split("_")[0]
    kind = "NAME" if "NAME" in FIELDS[field_idx] else "AMOUNT"
    print(f"  Row {row} {kind}: ({x}, {y})")

    update_canvas()
    field_idx += 1
    if field_idx < len(FIELDS):
        r = FIELDS[field_idx].split("ROW")[1].split("_")[0]
        k = "USERNAME" if "NAME" in FIELDS[field_idx] else "WAGERED AMOUNT"
        label_var.set(f"Click: Row {r} {k}  |  Right-click/Z = undo | S = save")
    else:
        label_var.set("All 20 positions set! Press S to save.")


def undo(event=None):
    global field_idx
    if field_idx <= 0:
        return
    field_idx -= 1
    if FIELDS[field_idx] in positions:
        del positions[FIELDS[field_idx]]
    update_canvas()
    r = FIELDS[field_idx].split("ROW")[1].split("_")[0]
    k = "USERNAME" if "NAME" in FIELDS[field_idx] else "WAGERED AMOUNT"
    label_var.set(f"Click: Row {r} {k}  |  Right-click/Z = undo | S = save")


def save(event=None):
    if len(positions) < 2:
        label_var.set("Need more positions!")
        return
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(positions, f, indent=2)
    print(f"\nSaved {len(positions)} positions to {OUTPUT_FILE}")
    label_var.set(f"SAVED! ({len(positions)} positions)")


base_img = Image.open(IMAGE_PATH).convert("RGBA")
orig_w, orig_h = base_img.size

root = tk.Tk()
root.title("Leaderboard Position Tool")

screen_h = min(root.winfo_screenheight() - 150, 850)
scale = screen_h / orig_h
display_w = int(orig_w * scale)
display_h = int(orig_h * scale)
scale_x = orig_w / display_w
scale_y = orig_h / display_h

photo = render_preview()

label_var = tk.StringVar(value="Click: Row 1 USERNAME  |  Right-click/Z = undo | S = save")
tk.Label(root, textvariable=label_var, font=("Arial", 13, "bold"), fg="white", bg="black").pack(fill="x")

canvas = tk.Canvas(root, width=display_w, height=display_h)
canvas.pack()
canvas.create_image(0, 0, anchor="nw", image=photo)
canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-3>", undo)
root.bind("z", undo)
root.bind("s", save)

root.mainloop()

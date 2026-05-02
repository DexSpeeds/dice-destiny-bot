"""
Rates Position Tool - Click where prices should appear
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json

IMAGE_PATH = "assets/rates.png"
OUTPUT_FILE = "rates_positions.json"

FIELDS = [
    "BUY_CRYPTO_PRICE",
    "BUY_OTHER_PRICE",
    "SELL_PRICE",
    "LAST_UPDATED",
]

PREVIEW = {
    "BUY_CRYPTO_PRICE": "$0.38 / M",
    "BUY_OTHER_PRICE": "$0.42 / M",
    "SELL_PRICE": "$0.32 / M",
    "LAST_UPDATED": "Updated: 2 min ago",
}

positions = {}
field_idx = 0


def render_preview():
    preview = base_img.copy()
    draw = ImageDraw.Draw(preview)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 28)
    except:
        font = ImageFont.load_default()
    gold = (220, 190, 100)
    for field, pos in positions.items():
        draw.text((pos['x'], pos['y']), PREVIEW.get(field, field), fill=gold, font=font)
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
    x, y = int(event.x * scale_x), int(event.y * scale_y)
    positions[FIELDS[field_idx]] = {"x": x, "y": y}
    print(f"  {FIELDS[field_idx]}: ({x}, {y})")
    update_canvas()
    field_idx += 1
    if field_idx < len(FIELDS):
        label_var.set(f"Click: {FIELDS[field_idx]} | Right-click/Z=undo | S=save")
    else:
        label_var.set("Done! Press S to save.")


def undo(event=None):
    global field_idx
    if field_idx <= 0: return
    field_idx -= 1
    if FIELDS[field_idx] in positions: del positions[FIELDS[field_idx]]
    update_canvas()
    label_var.set(f"Click: {FIELDS[field_idx]}")


def save(event=None):
    if positions:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(positions, f, indent=2)
        label_var.set(f"SAVED! ({len(positions)} positions)")


base_img = Image.open(IMAGE_PATH).convert("RGBA")
orig_w, orig_h = base_img.size
root = tk.Tk()
root.title("Rates Position Tool")
screen_h = min(root.winfo_screenheight() - 150, 850)
scale = screen_h / orig_h
display_w, display_h = int(orig_w * scale), int(orig_h * scale)
scale_x, scale_y = orig_w / display_w, orig_h / display_h
photo = render_preview()
label_var = tk.StringVar(value=f"Click: {FIELDS[0]}")
tk.Label(root, textvariable=label_var, font=("Arial", 13, "bold"), fg="white", bg="black").pack(fill="x")
canvas = tk.Canvas(root, width=display_w, height=display_h)
canvas.pack()
canvas.create_image(0, 0, anchor="nw", image=photo)
canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-3>", undo)
root.bind("z", undo)
root.bind("s", save)
root.mainloop()

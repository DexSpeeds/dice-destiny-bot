"""
Chip Position Tool - Click where each bet chip should be placed on the roulette table.
Shows a preview chip at each clicked position.
Right-click or Z to undo. S to save.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json

IMAGE_PATH = "assets/roulette_table.png"
OUTPUT_FILE = "roulette_chip_positions.json"

FIELDS = [
    "red",
    "black",
    "even",
    "odd",
    "low",       # 1-18
    "high",      # 19-36
    "dozen1",    # 1 to 12
    "dozen2",    # 13 to 24
    "dozen3",    # 25 to 36
]

LABELS = {
    "red": "RED chip",
    "black": "BLACK chip",
    "even": "EVEN chip",
    "odd": "ODD chip",
    "low": "1-18 chip",
    "high": "19-36 chip",
    "dozen1": "1st DOZEN chip",
    "dozen2": "2nd DOZEN chip",
    "dozen3": "3rd DOZEN chip",
}

positions = {}
field_idx = 0


def render_preview():
    preview = base_img.copy()
    draw = ImageDraw.Draw(preview)

    for field, pos in positions.items():
        cx, cy = pos['x'], pos['y']
        # Draw chip
        draw.ellipse([(cx-25, cy-25), (cx+25, cy+25)], fill=(160, 30, 30), outline=(255, 215, 0), width=4)
        draw.ellipse([(cx-19, cy-19), (cx+19, cy+19)], outline=(255, 215, 0, 180), width=2)
        # Label
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
        text = field.upper()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw//2, cy - 7), text, fill=(255, 255, 255), font=font)

    preview_resized = preview.resize((display_w, display_h), Image.LANCZOS)
    return ImageTk.PhotoImage(preview_resized)


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

    field = FIELDS[field_idx]
    positions[field] = {"x": x, "y": y}
    print(f"  {field}: ({x}, {y})")

    update_canvas()

    field_idx += 1
    if field_idx < len(FIELDS):
        label_var.set(f"Click where {LABELS[FIELDS[field_idx]]} goes  |  Right-click/Z = undo | S = save")
    else:
        label_var.set("All done! Press S to save.")


def undo(event=None):
    global field_idx
    if field_idx <= 0:
        return
    field_idx -= 1
    field = FIELDS[field_idx]
    if field in positions:
        del positions[field]
    print(f"  UNDO: {field}")
    update_canvas()
    label_var.set(f"Click where {LABELS[FIELDS[field_idx]]} goes  |  Right-click/Z = undo | S = save")


def save(event=None):
    if len(positions) >= 1:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(positions, f, indent=2)
        print(f"\nSaved to {OUTPUT_FILE}:")
        print(json.dumps(positions, indent=2))
        label_var.set(f"SAVED! ({len(positions)} positions)")


base_img = Image.open(IMAGE_PATH).convert("RGBA")
orig_w, orig_h = base_img.size

root = tk.Tk()
root.title("Chip Position Tool - Click where chips go")

screen_w = min(root.winfo_screenwidth() - 100, 1400)
scale = screen_w / orig_w
display_w = int(orig_w * scale)
display_h = int(orig_h * scale)
scale_x = orig_w / display_w
scale_y = orig_h / display_h

img_resized = base_img.resize((display_w, display_h), Image.LANCZOS)
photo = ImageTk.PhotoImage(img_resized)

label_var = tk.StringVar(value=f"Click where {LABELS[FIELDS[0]]} goes  |  Right-click/Z = undo | S = save")
label = tk.Label(root, textvariable=label_var, font=("Arial", 14, "bold"), fg="white", bg="black")
label.pack(fill="x")

canvas = tk.Canvas(root, width=display_w, height=display_h)
canvas.pack()
canvas.create_image(0, 0, anchor="nw", image=photo)
canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-3>", undo)
root.bind("z", undo)
root.bind("s", save)

print("Click where each chip should go on the table.")
print("Right-click/Z = undo | S = save\n")

root.mainloop()

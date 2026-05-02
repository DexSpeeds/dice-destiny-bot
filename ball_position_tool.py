"""
Ball Position Tool - Click on the roulette disk where the ball should land.
Click on the CENTER of the 0 slot (green). The tool calculates the radius
and uses it for all other numbers automatically.
Shows a preview ball at each position.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import json
import math

DISK_PATH = "assets/roulette_disk.png"
OUTPUT_FILE = "roulette_ball_config.json"

WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

ball_pos = None
step = 0  # 0 = click center, 1 = click ball on 0


def render_preview():
    preview = base_img.copy()
    draw = ImageDraw.Draw(preview)
    cx, cy = base_img.width // 2, base_img.height // 2

    # Draw center crosshair
    draw.line([(cx - 20, cy), (cx + 20, cy)], fill=(255, 255, 0), width=2)
    draw.line([(cx, cy - 20), (cx, cy + 20)], fill=(255, 255, 0), width=2)

    if ball_pos:
        bx, by = ball_pos
        # Calculate radius from center
        radius = math.sqrt((bx - cx) ** 2 + (by - cy) ** 2)
        # Calculate angle of the clicked position
        angle_0 = math.atan2(by - cy, bx - cx)

        # Draw ball on every number position
        slot_angle = 2 * math.pi / len(WHEEL_ORDER)
        for i, num in enumerate(WHEEL_ORDER):
            angle = angle_0 + i * slot_angle
            nx = int(cx + radius * math.cos(angle))
            ny = int(cy + radius * math.sin(angle))
            # Small dot for most numbers
            draw.ellipse([(nx - 5, ny - 5), (nx + 5, ny + 5)], fill=(255, 255, 255, 150))
            # Big ball for 0
            if num == 0:
                draw.ellipse([(nx - 12, ny - 12), (nx + 12, ny + 12)],
                             fill=(255, 255, 255), outline=(255, 215, 0), width=3)

        # Draw radius circle
        draw.ellipse([(int(cx - radius), int(cy - radius)),
                      (int(cx + radius), int(cy + radius))],
                     outline=(255, 215, 0, 100), width=1)

    preview_resized = preview.resize((display_w, display_h), Image.LANCZOS)
    return ImageTk.PhotoImage(preview_resized)


def update_canvas():
    global photo
    photo = render_preview()
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=photo)


def on_click(event):
    global ball_pos, step

    x = int(event.x * scale_x)
    y = int(event.y * scale_y)

    ball_pos = (x, y)
    cx, cy = base_img.width // 2, base_img.height // 2
    radius = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    angle = math.atan2(y - cy, x - cx)

    print(f"  Ball position: ({x}, {y})")
    print(f"  Radius from center: {radius:.0f}")
    print(f"  Angle: {math.degrees(angle):.1f} degrees")

    update_canvas()
    label_var.set(f"Ball at ({x},{y}) radius={radius:.0f}. Right-click to undo. S to save.")


def undo(event=None):
    global ball_pos
    ball_pos = None
    update_canvas()
    label_var.set("Click on the ball landing spot in the 0 (green) slot")


def save(event=None):
    if ball_pos is None:
        label_var.set("Click first!")
        return
    cx, cy = base_img.width // 2, base_img.height // 2
    bx, by = ball_pos
    radius = math.sqrt((bx - cx) ** 2 + (by - cy) ** 2)
    angle = math.atan2(by - cy, bx - cx)

    config = {
        "ball_radius": round(radius, 1),
        "zero_angle": round(math.degrees(angle), 1),
        "disk_center_x": cx,
        "disk_center_y": cy,
        "ball_x": bx,
        "ball_y": by,
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\nSaved to {OUTPUT_FILE}:")
    print(json.dumps(config, indent=2))
    label_var.set(f"SAVED! Radius={radius:.0f}, Angle={math.degrees(angle):.1f}°")


base_img = Image.open(DISK_PATH).convert("RGBA")
orig_w, orig_h = base_img.size

root = tk.Tk()
root.title("Ball Position Tool - Click where ball lands on 0")

screen_h = min(root.winfo_screenheight() - 150, 900)
scale = screen_h / orig_h
display_w = int(orig_w * scale)
display_h = int(orig_h * scale)
scale_x = orig_w / display_w
scale_y = orig_h / display_h

photo = render_preview()

label_var = tk.StringVar(value="Click on the ball landing spot in the 0 (green) slot")
label = tk.Label(root, textvariable=label_var, font=("Arial", 14, "bold"), fg="white", bg="black")
label.pack(fill="x")

canvas = tk.Canvas(root, width=display_w, height=display_h)
canvas.pack()
canvas.create_image(0, 0, anchor="nw", image=photo)
canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-3>", undo)
root.bind("z", undo)
root.bind("s", save)

print("Click where the ball should sit in the 0 slot.")
print("You'll see preview dots on all numbers.")
print("Right-click/Z = undo | S = save\n")

root.mainloop()

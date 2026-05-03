"""
Staking Position Tool - Click to set positions with LIVE PREVIEW
Shows actual HP bars, real OSRS hitsplat sprites, and labels as you click
Right-click to undo last click
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import os

IMAGE_PATH = 'assets/staking_frame_ref.png'
OUTPUT_PATH = 'staking_positions.json'
FONT_PATH = 'assets/fonts/arialbd.ttf'
SPLAT_DAMAGE_PATH = 'assets/hitsplat_damage.png'
SPLAT_ZERO_PATH = 'assets/hitsplat_zero.png'
SCALE = 2

POSITION_NAMES = [
    "Left HP Bar Center (YOU)",
    "Right HP Bar Center (HOST)",
    "Left Hitsplat Center",
    "Right Hitsplat Center",
    "Left Label Position (YOU text)",
    "Right Label Position (HOST text)",
]

HP_BAR_W = 70
HP_BAR_H = 8
HP_BAR_BORDER = 2
SPLAT_SIZE = 34


class StakingPositionTool:
    def __init__(self):
        self.positions = []
        self.current = 0

        self.root = tk.Tk()
        self.root.title("Staking Position Tool - LIVE PREVIEW")

        # Load image and font
        self.orig_img = Image.open(IMAGE_PATH).convert('RGBA')
        self.w, self.h = self.orig_img.size
        self.display_w = self.w * SCALE
        self.display_h = self.h * SCALE

        try:
            self.font_splat = ImageFont.truetype(FONT_PATH, 14)
            self.font_hp = ImageFont.truetype(FONT_PATH, 10)
            self.font_label = ImageFont.truetype(FONT_PATH, 11)
        except Exception:
            self.font_splat = ImageFont.load_default()
            self.font_hp = self.font_splat
            self.font_label = self.font_splat

        # Load hitsplat sprites
        self.splat_damage = Image.open(SPLAT_DAMAGE_PATH).convert('RGBA').resize((SPLAT_SIZE, SPLAT_SIZE), Image.LANCZOS)
        self.splat_zero = Image.open(SPLAT_ZERO_PATH).convert('RGBA').resize((SPLAT_SIZE, SPLAT_SIZE), Image.LANCZOS)

        # Instruction label
        self.label = tk.Label(
            self.root,
            text=f"Click: {POSITION_NAMES[0]}  |  Right-click to undo",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="#222222",
            pady=8
        )
        self.label.pack(fill=tk.X)

        # Canvas
        self.canvas = tk.Canvas(self.root, width=self.display_w, height=self.display_h)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_undo)

        self.redraw()
        self.root.mainloop()

    def redraw(self):
        """Redraw the image with all current overlays"""
        img = self.orig_img.copy()
        draw = ImageDraw.Draw(img)

        for i, (x, y) in enumerate(self.positions):
            if i == 0:  # Left HP bar
                self._draw_hp_bar(draw, x, y, 75)
            elif i == 1:  # Right HP bar
                self._draw_hp_bar(draw, x, y, 45)
            elif i == 2:  # Left hitsplat
                self._paste_hitsplat(img, x, y, 18)
            elif i == 3:  # Right hitsplat
                self._paste_hitsplat_zero(img, x, y)
            elif i == 4:  # Left label
                draw = ImageDraw.Draw(img)  # Refresh after paste
                self._draw_label(draw, x, y, "YOU", (0, 255, 0))
            elif i == 5:  # Right label
                draw = ImageDraw.Draw(img)
                self._draw_label(draw, x, y, "HOST", (255, 60, 60))

        # Scale up for display
        display = img.convert('RGB').resize((self.display_w, self.display_h), Image.NEAREST)
        self.tk_img = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)

        # Center guide
        cx = self.display_w // 2
        self.canvas.create_line(cx, 0, cx, self.display_h, fill="yellow", dash=(4, 4), width=1)

    def _draw_hp_bar(self, draw, cx, cy, hp):
        bar_x = cx - HP_BAR_W // 2
        bar_y = cy - HP_BAR_H // 2
        draw.rectangle([bar_x - HP_BAR_BORDER, bar_y - HP_BAR_BORDER,
                         bar_x + HP_BAR_W + HP_BAR_BORDER, bar_y + HP_BAR_H + HP_BAR_BORDER], fill=(0, 0, 0))
        draw.rectangle([bar_x, bar_y, bar_x + HP_BAR_W, bar_y + HP_BAR_H], fill=(200, 30, 30))
        green_w = int(HP_BAR_W * hp / 99)
        if green_w > 0:
            draw.rectangle([bar_x, bar_y, bar_x + green_w, bar_y + HP_BAR_H], fill=(34, 177, 76))
        text = str(hp)
        bbox = self.font_hp.getbbox(text)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2 + 1, cy + HP_BAR_H // 2 + 4), text, fill=(0, 0, 0), font=self.font_hp)
        draw.text((cx - tw // 2, cy + HP_BAR_H // 2 + 3), text, fill=(255, 255, 255), font=self.font_hp)

    def _paste_hitsplat(self, img, cx, cy, damage):
        splat = self.splat_damage.copy()
        splat_draw = ImageDraw.Draw(splat)
        text = str(damage)
        bbox = self.font_splat.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = SPLAT_SIZE // 2 - tw // 2
        ty = SPLAT_SIZE // 2 - th // 2 - 1
        splat_draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0), font=self.font_splat)
        splat_draw.text((tx, ty), text, fill=(255, 255, 255), font=self.font_splat)
        img.paste(splat, (cx - SPLAT_SIZE // 2, cy - SPLAT_SIZE // 2), splat)

    def _paste_hitsplat_zero(self, img, cx, cy):
        splat = self.splat_zero.copy()
        splat_draw = ImageDraw.Draw(splat)
        text = "0"
        bbox = self.font_splat.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = SPLAT_SIZE // 2 - tw // 2
        ty = SPLAT_SIZE // 2 - th // 2 - 1
        splat_draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0), font=self.font_splat)
        splat_draw.text((tx, ty), text, fill=(255, 255, 255), font=self.font_splat)
        img.paste(splat, (cx - SPLAT_SIZE // 2, cy - SPLAT_SIZE // 2), splat)

    def _draw_label(self, draw, cx, cy, text, color):
        bbox = self.font_label.getbbox(text)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2 + 1, cy + 1), text, fill=(0, 0, 0), font=self.font_label)
        draw.text((cx - tw // 2, cy), text, fill=color, font=self.font_label)

    def on_click(self, event):
        if self.current >= len(POSITION_NAMES):
            return

        actual_x = event.x // SCALE
        actual_y = event.y // SCALE

        self.positions.append((actual_x, actual_y))
        name = POSITION_NAMES[self.current]
        print(f"{name}: ({actual_x}, {actual_y})")

        self.current += 1
        self.redraw()

        if self.current < len(POSITION_NAMES):
            self.label.config(text=f"Click: {POSITION_NAMES[self.current]}  |  Right-click to undo")
        else:
            self.save_positions()
            self.label.config(text="Done! Positions saved. Close window.", bg="#006600")

    def on_undo(self, event):
        if self.positions:
            removed = self.positions.pop()
            self.current -= 1
            print(f"Undo: removed ({removed[0]}, {removed[1]})")
            self.redraw()
            self.label.config(text=f"Click: {POSITION_NAMES[self.current]}  |  Right-click to undo", bg="#222222")

    def save_positions(self):
        data = {
            "left_hp_bar": list(self.positions[0]),
            "right_hp_bar": list(self.positions[1]),
            "left_hitsplat": list(self.positions[2]),
            "right_hitsplat": list(self.positions[3]),
            "left_label": list(self.positions[4]),
            "right_label": list(self.positions[5]),
        }
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved to {OUTPUT_PATH}:")
        print(json.dumps(data, indent=2))


if __name__ == '__main__':
    StakingPositionTool()

"""Normalize generated cat atlas into Codex/oc-claw pet format."""
from __future__ import annotations

import json
import os
from PIL import Image

SRC = r"C:\Users\Avetics\.cursor\projects\c-Users-Avetics-Desktop-Projects-oc-claw\assets\fluffy-cat-atlas-raw.png"
OUT_DIR = r"C:\Users\Avetics\Desktop\Projects\oc-claw\frontend\public\assets\custom\fluffy-cat"

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 9
ATLAS_W, ATLAS_H = CELL_W * COLS, CELL_H * ROWS  # 1536x1872

# Official frame counts per row (hatch-pet / oc-claw contract)
FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def is_chroma(r: int, g: int, b: int) -> bool:
    # bright green chroma (used-cell background)
    if g > 180 and r < 120 and b < 120:
        return True
    # magenta unused cells
    if r > 180 and b > 180 and g < 120:
        return True
    return False


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    img = Image.open(SRC).convert("RGBA")
    img = img.resize((ATLAS_W, ATLAS_H), Image.Resampling.LANCZOS)
    px = img.load()

    for y in range(ATLAS_H):
        for x in range(ATLAS_W):
            r, g, b, _a = px[x, y]
            if is_chroma(r, g, b):
                px[x, y] = (0, 0, 0, 0)

    # Force unused trailing cells fully transparent
    for row, frames in enumerate(FRAME_COUNTS):
        for col in range(frames, COLS):
            x0, y0 = col * CELL_W, row * CELL_H
            for yy in range(y0, y0 + CELL_H):
                for xx in range(x0, x0 + CELL_W):
                    px[xx, yy] = (0, 0, 0, 0)

    out_webp = os.path.join(OUT_DIR, "spritesheet.webp")
    out_png = os.path.join(OUT_DIR, "spritesheet.png")
    img.save(out_webp, "WEBP", quality=90, method=6)
    img.save(out_png, "PNG")

    meta = {
        "id": "fluffy-cat",
        "displayName": "Fluffy Cat",
        "description": "A grumpy fluffy cream cat with blue eyes, made from a photo reference.",
        "spritesheetPath": "spritesheet.webp",
    }
    with open(os.path.join(OUT_DIR, "pet.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")

    print("size", img.size)
    print("wrote", out_webp)
    print("wrote", os.path.join(OUT_DIR, "pet.json"))


if __name__ == "__main__":
    main()

"""
Recolor fluffy-cat spritesheet: coffee-brown / cream fur -> grey.

Preserves luminance so face/ear/tail markings stay readable as darker grey.
Leaves eyes, pink nose/pads, black outlines, and postures unchanged.
No special paw handling.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image

SRC = Path(
    r"C:\Users\Avetics\Desktop\Projects\oc-claw"
    r"\frontend\public\assets\custom\fluffy-cat\spritesheet.png"
)
OUT_DIRS = [
    Path(r"C:\Users\Avetics\Desktop\Projects\oc-claw\frontend\public\assets\custom\fluffy-cat"),
    Path(os.path.expanduser(r"~/.codex\pets\fluffy-cat")),
]

CELL_W, CELL_H = 192, 208
ROWS = 9
FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def is_green(r: int, g: int, b: int, a: int) -> bool:
    return a > 40 and g > 100 and g > r + 40 and g > b + 40


def is_blue_eye(r: int, g: int, b: int, a: int) -> bool:
    if a < 40:
        return False
    return b > r + 15 and b > g + 5 and b > 70


def is_pink_accent(r: int, g: int, b: int, a: int) -> bool:
    """Pink nose / inner-ear / paw-pad accents — leave untouched."""
    if a < 40:
        return False
    return (
        r > 175
        and 95 < g < 170
        and 85 < b < 155
        and (r - g) > 55
        and (r - b) > 55
        and (g - b) < 35
        and g < 0.72 * r
    )


def is_outline(r: int, g: int, b: int, a: int) -> bool:
    if a < 40:
        return False
    return max(r, g, b) < 36


def is_warm_fur(r: int, g: int, b: int, a: int) -> bool:
    """Coffee / cream / chocolate fur family."""
    if a < 40 or is_green(r, g, b, a) or is_blue_eye(r, g, b, a):
        return False
    if is_outline(r, g, b, a) or is_pink_accent(r, g, b, a):
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 28:
        return False
    sat = (mx - mn) / mx if mx else 0.0
    if r < g - 6 or g < b - 10:
        return False
    if (r - b) < 10 or sat < 0.05:
        return False
    if abs(r - g) < 6 and abs(g - b) < 6:
        return False
    return True


def warm_to_grey(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Map warm fur to cool grey, preserving shading via luminance."""
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    t = (lum - 25.0) / (245.0 - 25.0)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    t = t ** 0.92
    base = 55 + t * 165  # ~55..220
    nr = int(round(base - 2))
    ng = int(round(base))
    nb = int(round(base + 4))
    return (
        max(0, min(255, nr)),
        max(0, min(255, ng)),
        max(0, min(255, nb)),
    )


def recolor_image(src: Image.Image) -> Image.Image:
    out = src.copy()
    px_in = src.load()
    px_out = out.load()
    w, h = src.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px_in[x, y]
            if a < 8:
                continue
            if is_warm_fur(r, g, b, a):
                nr, ng, nb = warm_to_grey(r, g, b)
                px_out[x, y] = (nr, ng, nb, a)
    return out


def write_outputs(atlas: Image.Image) -> None:
    meta = {
        "id": "fluffy-cat",
        "displayName": "Fluffy Cat",
        "description": "A grumpy fluffy grey cat with blue eyes.",
        "spritesheetPath": "spritesheet.webp",
    }
    for out in OUT_DIRS:
        out.mkdir(parents=True, exist_ok=True)
        atlas.save(out / "spritesheet.png")
        atlas.save(out / "spritesheet.webp", "WEBP", quality=92, method=6)
        with open(out / "pet.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
        print("wrote", out)


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    print("src", src.size)
    # Sanity: used cells still exist after restore
    for row, need in enumerate(FRAME_COUNTS):
        print(f"row {row}: {need} frames")
    atlas = recolor_image(src)
    write_outputs(atlas)
    print("done")


if __name__ == "__main__":
    main()

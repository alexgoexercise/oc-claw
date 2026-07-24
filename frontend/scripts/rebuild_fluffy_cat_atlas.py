"""
Rebuild fluffy-cat into a true uniform Codex/oc-claw atlas (1536x1872,
8x9 cells of 192x208).

The AI raw sheet is NOT a uniform grid (variable cell widths/heights).
SpritePet assumes fixed cells, so a naive resize shows multiple cats.
This script detects each sprite via content-density projections, then
aspect-fits every sprite into a proper cell.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from PIL import Image

RAW = Path(
    r"C:\Users\Avetics\.cursor\projects\c-Users-Avetics-Desktop-Projects-oc-claw"
    r"\assets\fluffy-cat-atlas-raw.png"
)
OUT_DIRS = [
    Path(r"C:\Users\Avetics\Desktop\Projects\oc-claw\frontend\public\assets\custom\fluffy-cat"),
    Path(os.path.expanduser(r"~/.codex/pets/fluffy-cat")),
]

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 9
ATLAS_W, ATLAS_H = CELL_W * COLS, CELL_H * ROWS
FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def is_green(r: int, g: int, b: int) -> bool:
    return g > 160 and r < 140 and b < 140 and g > r + 40 and g > b + 40


def is_magenta(r: int, g: int, b: int) -> bool:
    return r > 160 and b > 160 and g < 140


def is_content(r: int, g: int, b: int, a: int) -> bool:
    if a < 8:
        return False
    if is_green(r, g, b) or is_magenta(r, g, b):
        return False
    # thin white grid lines
    if r > 220 and g > 220 and b > 220:
        return False
    return True


def punch_chroma(sprite: Image.Image) -> Image.Image:
    sp = sprite.convert("RGBA")
    px = sp.load()
    w, h = sp.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 8 or is_green(r, g, b) or is_magenta(r, g, b) or (
                r > 220 and g > 220 and b > 220
            ):
                px[x, y] = (0, 0, 0, 0)
    return sp


def tight_crop(sprite: Image.Image) -> Image.Image:
    sp = punch_chroma(sprite)
    bbox = sp.getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return sp.crop(bbox)


def fit_into_cell(sprite: Image.Image) -> Image.Image:
    """Aspect-fit into 192x208, bottom-centered — same contract as hatch-pet cells."""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    sp = tight_crop(sprite)
    sw, sh = sp.size
    if sw <= 0 or sh <= 0:
        return cell
    max_w = int(CELL_W * 0.90)
    max_h = int(CELL_H * 0.90)
    scale = min(max_w / sw, max_h / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    resized = sp.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (CELL_W - nw) // 2
    y = CELL_H - nh - max(4, (CELL_H - nh) // 8)
    if y < 2:
        y = 2
    cell.alpha_composite(resized, (x, y))
    return cell


def detect_row_bands(px, w: int, h: int) -> list[tuple[int, int]]:
    crow = [
        sum(1 for x in range(w) if is_content(*px[x, y]))
        for y in range(h)
    ]
    thr = 40
    bands: list[tuple[int, int]] = []
    y = 0
    while y < h:
        while y < h and crow[y] < thr:
            y += 1
        if y >= h:
            break
        y0 = y
        while y < h and crow[y] >= thr:
            y += 1
        # Drop 1–2px noise bands between real rows
        if (y - y0) >= 40:
            bands.append((y0, y))
    return bands


def detect_slots(px, w: int, y0: int, y1: int) -> list[tuple[int, int]]:
    ccol = [
        sum(1 for y in range(y0, y1) if is_content(*px[x, y]))
        for x in range(w)
    ]
    cthr = max(3, (y1 - y0) // 25)
    slots: list[tuple[int, int]] = []
    x = 0
    while x < w:
        while x < w and ccol[x] < cthr:
            x += 1
        if x >= w:
            break
        x0 = x
        while x < w and ccol[x] >= cthr:
            x += 1
        # Merge tiny gaps caused by grid lines cutting through a sprite
        while True:
            gap = 0
            while x + gap < w and ccol[x + gap] < cthr:
                gap += 1
            if 0 < gap <= 8 and x + gap < w and ccol[x + gap] >= cthr:
                x += gap
                while x < w and ccol[x] >= cthr:
                    x += 1
            else:
                break
        # Drop 1px noise slots
        if (x - x0) >= 40:
            slots.append((x0, x))

    # Split merged double-wide slots (two cats glued by weak gap)
    if not slots:
        return slots
    widths = [b - a for a, b in slots]
    widths_sorted = sorted(widths)
    median = widths_sorted[len(widths_sorted) // 2]
    split: list[tuple[int, int]] = []
    for a, b in slots:
        width = b - a
        if width > int(median * 1.55):
            # Find lowest-content valley near the midpoint
            mid = (a + b) // 2
            search = max(8, width // 6)
            best_x = mid
            best_v = 10**9
            for x in range(max(a + 10, mid - search), min(b - 10, mid + search) + 1):
                # local average to avoid single-pixel spikes
                v = sum(ccol[max(a, x - 2) : min(b, x + 3)]) 
                if v < best_v:
                    best_v = v
                    best_x = x
            split.append((a, best_x))
            split.append((best_x, b))
            print(f"    split wide slot {a}-{b} (w={width}) at {best_x}")
        else:
            split.append((a, b))
    return [(a, b) for a, b in split if (b - a) >= 40]


def facing_bias(cell: Image.Image) -> int:
    px = cell.load()
    w, h = cell.size
    left = right = 0
    mid = w // 2
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 20:
                if x < mid:
                    left += 1
                else:
                    right += 1
    return right - left


def extract_rows(raw: Image.Image) -> list[list[Image.Image]]:
    rgba = raw.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    bands = detect_row_bands(px, w, h)
    print(f"detected {len(bands)} row bands")
    if len(bands) != ROWS:
        raise SystemExit(f"expected {ROWS} rows, got {len(bands)}: {bands}")

    rows: list[list[Image.Image]] = []
    for ri, (y0, y1) in enumerate(bands):
        # Expand band slightly into green padding if available
        ye0 = max(0, y0 - 2)
        ye1 = min(h, y1 + 2)
        slots = detect_slots(px, w, ye0, ye1)
        print(f"  row {ri}: {len(slots)} sprites  band=({y0},{y1}) widths={[x1-x0 for x0,x1 in slots]}")
        sprites: list[Image.Image] = []
        for x0, x1 in slots:
            crop = rgba.crop((max(0, x0 - 2), ye0, min(w, x1 + 2), ye1))
            sprites.append(tight_crop(crop))
        rows.append(sprites)
    return rows


def compose(rows: list[list[Image.Image]]) -> Image.Image:
    # Ensure row1 = run-right, row2 = run-left
    if len(rows) >= 3 and rows[1] and rows[2]:
        b1 = facing_bias(fit_into_cell(rows[1][0]))
        b2 = facing_bias(fit_into_cell(rows[2][0]))
        print(f"facing bias row1={b1} row2={b2}")
        if b1 < b2:
            rows[1], rows[2] = rows[2], rows[1]
            print("swapped run rows")

    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))
    for row, need in enumerate(FRAME_COUNTS):
        sprites = list(rows[row]) if row < len(rows) else []
        if not sprites:
            print(f"WARNING: row {row} has no sprites")
            continue
        if len(sprites) < need:
            sprites = sprites + [sprites[-1]] * (need - len(sprites))
            print(f"  padded row {row} to {need} frames")
        sprites = sprites[:need]
        for col, sp in enumerate(sprites):
            atlas.alpha_composite(fit_into_cell(sp), (col * CELL_W, row * CELL_H))
        print(f"placed row {row}: {len(sprites)}/{need}")
    return atlas


def write_package(atlas: Image.Image) -> None:
    meta = {
        "id": "fluffy-cat",
        "displayName": "Fluffy Cat",
        "description": "A grumpy fluffy cream cat with blue eyes, made from a photo reference.",
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


def verify(atlas: Image.Image) -> None:
    """Each used cell must contain content; unused cells must be empty."""
    px = atlas.load()
    for row, need in enumerate(FRAME_COUNTS):
        for col in range(COLS):
            x0, y0 = col * CELL_W, row * CELL_H
            count = 0
            for y in range(y0, y0 + CELL_H):
                for x in range(x0, x0 + CELL_W):
                    if px[x, y][3] > 20:
                        count += 1
            if col < need and count < 400:
                print(f"WARNING sparse cell r{row}c{col} alpha={count}")
            if col >= need and count > 50:
                print(f"WARNING unused cell has content r{row}c{col} alpha={count}")
    print("verify done; atlas", atlas.size)


def main() -> None:
    raw = Image.open(RAW)
    print("raw size", raw.size)
    rows = extract_rows(raw)
    atlas = compose(rows)
    assert atlas.size == (ATLAS_W, ATLAS_H)
    write_package(atlas)
    verify(atlas)


if __name__ == "__main__":
    main()

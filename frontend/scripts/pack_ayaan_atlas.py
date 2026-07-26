"""
Re-pack Ayaan raw atlas into clean 192x208 cells.

The AI raw sheet is NOT a perfect uniform grid — sprites drift and wide
poses (lying down) span multiple naive slots. This script detects each
sprite via content-density projections (same approach as
rebuild_fluffy_cat_atlas.py), then aspect-fits into hatch-pet cells.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "scripts/_ayaan_build/ayaan_atlas_raw.png"
OUT_DIR = ROOT / "public/assets/custom/ayaan"
AUDIT = ROOT / "scripts/_ayaan_build/audit"

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 9
ATLAS_W, ATLAS_H = CELL_W * COLS, CELL_H * ROWS
FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def is_green(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 8:
        return True
    return g > 140 and g > r + 40 and g > b + 40


def is_magenta(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 8:
        return False
    return r > 160 and b > 160 and g < 140


def is_content(r: int, g: int, b: int, a: int) -> bool:
    if a < 8:
        return False
    if is_green(r, g, b, a) or is_magenta(r, g, b, a):
        return False
    # near-white / near-black noise only — keep character pixels
    return True


def punch_chroma(sprite: Image.Image) -> Image.Image:
    sp = sprite.convert("RGBA")
    px = sp.load()
    w, h = sp.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if is_green(r, g, b, a) or is_magenta(r, g, b, a):
                px[x, y] = (0, 0, 0, 0)
            # Green fringe leftover from chroma key (semi-transparent / dimmer)
            elif a < 180 and g > r + 15 and g > b + 15 and g > 60:
                px[x, y] = (0, 0, 0, 0)
            elif g > 90 and g > r + 25 and g > b + 25:
                px[x, y] = (0, 0, 0, 0)
    return sp


def keep_largest_component(sprite: Image.Image) -> Image.Image:
    """Drop disconnected bleed fragments."""
    w, h = sprite.size
    px = sprite.load()
    visited = [[False] * w for _ in range(h)]
    comps: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if visited[y][x] or px[x, y][3] < 20:
                continue
            q = deque([(x, y)])
            visited[y][x] = True
            pixels: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                pixels.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny][3] >= 20:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            comps.append(pixels)
    if not comps:
        return sprite
    comps.sort(key=len, reverse=True)
    # Keep main blob + nearby fragments (arms/tears within 12px of bbox)
    keep = set(comps[0])
    xs = [p[0] for p in comps[0]]
    ys = [p[1] for p in comps[0]]
    x0, x1, y0, y1 = min(xs) - 12, max(xs) + 12, min(ys) - 12, max(ys) + 12
    for comp in comps[1:]:
        if len(comp) < 8:
            continue
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in comp):
            keep.update(comp)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    opx = out.load()
    for x, y in keep:
        opx[x, y] = px[x, y]
    return out


def tight_crop(sprite: Image.Image) -> Image.Image:
    sp = keep_largest_component(punch_chroma(sprite))
    bbox = sp.getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return sp.crop(bbox)


def fit_into_cell(sprite: Image.Image) -> Image.Image:
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    sp = tight_crop(sprite) if sprite.mode == "RGBA" else sprite
    # If already cropped RGBA with content, use as-is after punch
    if sp.getbbox() is None:
        sp = tight_crop(sprite)
    sw, sh = sp.size
    if sw <= 0 or sh <= 0:
        return cell
    max_w = int(CELL_W * 0.92)
    max_h = int(CELL_H * 0.92)
    scale = min(max_w / sw, max_h / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    # NEAREST keeps pixel edges; LANCZOS if source was already soft
    resized = sp.resize((nw, nh), Image.Resampling.NEAREST)
    x = (CELL_W - nw) // 2
    y = CELL_H - nh - max(4, (CELL_H - nh) // 8)
    if y < 2:
        y = 2
    cell.alpha_composite(resized, (x, y))
    return cell


def detect_row_bands(px, w: int, h: int) -> list[tuple[int, int]]:
    crow = [sum(1 for x in range(w) if is_content(*px[x, y])) for y in range(h)]
    thr = max(25, w // 40)
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
        if (y - y0) >= 30:
            bands.append((y0, y))
    return bands


def detect_slots(px, w: int, y0: int, y1: int) -> list[tuple[int, int]]:
    ccol = [sum(1 for y in range(y0, y1) if is_content(*px[x, y])) for x in range(w)]
    cthr = max(3, (y1 - y0) // 30)
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
        # Merge tiny gaps (grid lines / green speckles cutting a sprite)
        while True:
            gap = 0
            while x + gap < w and ccol[x + gap] < cthr:
                gap += 1
            if 0 < gap <= 10 and x + gap < w and ccol[x + gap] >= cthr:
                x += gap
                while x < w and ccol[x] >= cthr:
                    x += 1
            else:
                break
        if (x - x0) >= 28:
            slots.append((x0, x))

    if not slots:
        return slots

    # Split merged double-wide slots (two cats glued / lying pose spanning 2)
    widths = [b - a for a, b in slots]
    widths_sorted = sorted(widths)
    median = widths_sorted[len(widths_sorted) // 2]
    split: list[tuple[int, int]] = []
    for a, b in slots:
        width = b - a
        # Only split if clearly wider than a typical standing sprite
        if width > int(median * 1.65) and width > 90:
            mid = (a + b) // 2
            search = max(8, width // 5)
            best_x = mid
            best_v = 10**9
            for x in range(max(a + 12, mid - search), min(b - 12, mid + search) + 1):
                v = sum(ccol[max(a, x - 2) : min(b, x + 3)])
                if v < best_v:
                    best_v = v
                    best_x = x
            left_w = best_x - a
            right_w = b - best_x
            # Prefer keeping one wide sprite if valley is weak (lying down)
            # Valley must be meaningfully emptier than median column density
            dens = sorted(ccol[a:b])
            med_d = dens[len(dens) // 2] if dens else 0
            if best_v < med_d * 0.45 and left_w >= 28 and right_w >= 28:
                split.append((a, best_x))
                split.append((best_x, b))
                print(f"    split wide slot {a}-{b} (w={width}) at {best_x}")
            else:
                split.append((a, b))
                print(f"    keep wide slot {a}-{b} (w={width}) as one sprite")
        else:
            split.append((a, b))
    return [(a, b) for a, b in split if (b - a) >= 28]


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
    print(f"detected {len(bands)} row bands: {bands}")
    if len(bands) != ROWS:
        # If we got more bands (magenta separators counting?), merge tiny ones
        # or fall back to equal horizontal slices guided by magenta/green gaps
        if len(bands) > ROWS:
            # Keep the tallest ROWS bands
            bands = sorted(bands, key=lambda b: b[1] - b[0], reverse=True)[:ROWS]
            bands = sorted(bands, key=lambda b: b[0])
            print(f"trimmed to {len(bands)} tallest bands")
        if len(bands) != ROWS:
            raise SystemExit(f"expected {ROWS} rows, got {len(bands)}: {bands}")

    rows: list[list[Image.Image]] = []
    for ri, (y0, y1) in enumerate(bands):
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
    if len(rows) >= 3 and rows[1] and rows[2]:
        b1 = facing_bias(fit_into_cell(rows[1][0]))
        b2 = facing_bias(fit_into_cell(rows[2][0]))
        print(f"facing bias row1={b1} row2={b2}")
        if b1 < 0 and b2 < 0:
            rows[1] = [s.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for s in rows[1]]
            print("flipped row1 to face right")
        elif b1 < b2:
            rows[1], rows[2] = rows[2], rows[1]
            print("swapped run rows")
            b1 = facing_bias(fit_into_cell(rows[1][0]))
            if b1 < 0:
                rows[1] = [s.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for s in rows[1]]
                print("flipped row1 after swap")

    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))
    for row, need in enumerate(FRAME_COUNTS):
        sprites = list(rows[row]) if row < len(rows) else []
        usable = [s for s in sprites if s.getbbox()]
        if len(usable) < need:
            if usable:
                usable = usable + [usable[-1]] * (need - len(usable))
                print(f"  padded row {row} to {need}")
            else:
                print(f"  WARNING: row {row} empty")
                continue
        usable = usable[:need]
        for col, sp in enumerate(usable):
            atlas.alpha_composite(fit_into_cell(sp), (col * CELL_W, row * CELL_H))
        print(f"placed row {row}: {len(usable)}/{need}")
    return atlas


def write_package(atlas: Image.Image) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT_DIR / "spritesheet.png")
    atlas.save(OUT_DIR / "spritesheet.webp", "WEBP", quality=92, method=6)
    meta = {
        "id": "ayaan",
        "displayName": "Ayaan",
        "description": "A cheerful pixel-art desktop companion of Ayaan in a deep blue tee.",
        "spritesheetPath": "spritesheet.webp",
    }
    with open(OUT_DIR / "pet.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print("wrote", OUT_DIR)


def write_audit(atlas: Image.Image) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    for row, need in enumerate(FRAME_COUNTS):
        strip = Image.new("RGBA", (CELL_W * need, CELL_H), (20, 20, 20, 255))
        for col in range(need):
            cell = atlas.crop((col * CELL_W, row * CELL_H, (col + 1) * CELL_W, (row + 1) * CELL_H))
            strip.alpha_composite(cell, (col * CELL_W, 0))
        strip.save(AUDIT / f"fixed_row{row}_strip.png")
    print("audit strips written to", AUDIT)


def verify(atlas: Image.Image) -> None:
    px = atlas.load()
    issues = 0
    for row, need in enumerate(FRAME_COUNTS):
        for col in range(COLS):
            x0, y0 = col * CELL_W, row * CELL_H
            count = sum(
                1
                for y in range(y0, y0 + CELL_H)
                for x in range(x0, x0 + CELL_W)
                if px[x, y][3] > 20
            )
            edge_l = sum(1 for y in range(y0, y0 + CELL_H) if px[x0, y][3] > 40)
            edge_r = sum(1 for y in range(y0, y0 + CELL_H) if px[x0 + CELL_W - 1, y][3] > 40)
            if col < need:
                if count < 400:
                    print(f"WARNING sparse r{row}c{col} alpha={count}")
                    issues += 1
                if edge_l > 60 or edge_r > 60:
                    print(f"WARNING edge-touch r{row}c{col} L={edge_l} R={edge_r}")
                    issues += 1
            elif count > 50:
                print(f"WARNING unused has content r{row}c{col} alpha={count}")
                issues += 1
    print(f"verify done; atlas={atlas.size} issues={issues}")


def main() -> None:
    raw = Image.open(RAW)
    print("raw size", raw.size)
    rows = extract_rows(raw)
    atlas = compose(rows)
    assert atlas.size == (ATLAS_W, ATLAS_H)
    write_package(atlas)
    write_audit(atlas)
    verify(atlas)


if __name__ == "__main__":
    main()

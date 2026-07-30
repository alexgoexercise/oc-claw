"""
Patch the Alex atlas:
1. Replace row 0, col 1 (wink) with a proper both-eyes-blink frame
2. Replace row 7 (walking) with phone-scrolling sprites

Uses the same tight_crop / fit_into_cell / punch_chroma logic from
pack_companion_atlas.py so the new cells match the existing ones.
"""
from __future__ import annotations
from pathlib import Path
from collections import deque
from PIL import Image

CELL_W, CELL_H = 192, 208
BUILD = Path(__file__).resolve().parent / "_alex_build"
ATLAS_PATH = Path(__file__).resolve().parents[1] / "public" / "assets" / "custom" / "alex" / "spritesheet.png"
WEBP_PATH = ATLAS_PATH.with_suffix(".webp")


def is_green(r, g, b, a=255):
    if a < 8: return True
    return g > 140 and g > r + 40 and g > b + 40

def is_magenta(r, g, b, a=255):
    if a < 8: return False
    return r > 160 and b > 160 and g < 140

def is_content(r, g, b, a):
    if a < 8: return False
    if is_green(r, g, b, a) or is_magenta(r, g, b, a): return False
    return True

def punch_chroma(sprite):
    sp = sprite.convert("RGBA")
    px = sp.load()
    w, h = sp.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if is_green(r, g, b, a) or is_magenta(r, g, b, a):
                px[x, y] = (0, 0, 0, 0)
            elif a < 180 and g > r + 15 and g > b + 15 and g > 60:
                px[x, y] = (0, 0, 0, 0)
            elif g > 90 and g > r + 25 and g > b + 25:
                px[x, y] = (0, 0, 0, 0)
    return sp

def keep_largest_component(sprite):
    w, h = sprite.size
    px = sprite.load()
    visited = [[False]*w for _ in range(h)]
    comps = []
    for y in range(h):
        for x in range(w):
            if visited[y][x] or px[x, y][3] < 20: continue
            q = deque([(x, y)])
            visited[y][x] = True
            pixels = []
            while q:
                cx, cy = q.popleft()
                pixels.append((cx, cy))
                for nx, ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                    if 0<=nx<w and 0<=ny<h and not visited[ny][nx] and px[nx,ny][3]>=20:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            comps.append(pixels)
    if not comps: return sprite
    comps.sort(key=len, reverse=True)
    keep = set(comps[0])
    xs = [p[0] for p in comps[0]]
    ys = [p[1] for p in comps[0]]
    x0, x1, y0, y1 = min(xs)-12, max(xs)+12, min(ys)-12, max(ys)+12
    for comp in comps[1:]:
        if len(comp) < 8: continue
        if any(x0<=x<=x1 and y0<=y<=y1 for x, y in comp):
            keep.update(comp)
    out = Image.new("RGBA", (w, h), (0,0,0,0))
    opx = out.load()
    for x, y in keep:
        opx[x, y] = px[x, y]
    return out

def tight_crop(sprite):
    sp = keep_largest_component(punch_chroma(sprite))
    bbox = sp.getbbox()
    if not bbox: return Image.new("RGBA", (1, 1), (0,0,0,0))
    return sp.crop(bbox)

def fit_into_cell(sprite):
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0,0,0,0))
    sp = tight_crop(sprite) if sprite.mode == "RGBA" else sprite
    if sp.getbbox() is None:
        sp = tight_crop(sprite)
    sw, sh = sp.size
    if sw <= 0 or sh <= 0: return cell
    max_w = int(CELL_W * 0.92)
    max_h = int(CELL_H * 0.92)
    scale = min(max_w / sw, max_h / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    resized = sp.resize((nw, nh), Image.Resampling.NEAREST)
    x = (CELL_W - nw) // 2
    y = CELL_H - nh - max(4, (CELL_H - nh) // 8)
    if y < 2: y = 2
    cell.alpha_composite(resized, (x, y))
    return cell

def detect_slots(px, w, y0, y1):
    ccol = [sum(1 for y in range(y0, y1) if is_content(*px[x, y])) for x in range(w)]
    cthr = max(3, (y1 - y0) // 30)
    slots = []
    x = 0
    while x < w:
        while x < w and ccol[x] < cthr: x += 1
        if x >= w: break
        x0s = x
        while x < w and ccol[x] >= cthr: x += 1
        while True:
            gap = 0
            while x + gap < w and ccol[x + gap] < cthr: gap += 1
            if 0 < gap <= 10 and x + gap < w and ccol[x + gap] >= cthr:
                x += gap
                while x < w and ccol[x] >= cthr: x += 1
            else: break
        if (x - x0s) >= 28:
            slots.append((x0s, x))
    return slots


def main():
    atlas = Image.open(ATLAS_PATH).convert("RGBA")
    print(f"loaded atlas {atlas.size}")

    # --- Fix 1: Replace row 0 col 1 with blink frame ---
    blink = Image.open(BUILD / "alex_blink_fix.png").convert("RGBA")
    blink_cell = fit_into_cell(blink)
    atlas.paste(Image.new("RGBA", (CELL_W, CELL_H), (0,0,0,0)), (1*CELL_W, 0*CELL_H))
    atlas.alpha_composite(blink_cell, (1*CELL_W, 0*CELL_H))
    print("patched row 0 col 1 (blink)")

    # --- Fix 2: Replace row 7 with phone-scrolling sprites ---
    phone_strip = Image.open(BUILD / "alex_phone_row.png").convert("RGBA")
    pw, ph = phone_strip.size
    ppx = phone_strip.load()

    # Detect sprite slots in the strip
    crow = [sum(1 for x in range(pw) if is_content(*ppx[x, y])) for y in range(ph)]
    thr = max(25, pw // 40)
    y = 0
    while y < ph and crow[y] < thr: y += 1
    y0 = y
    while y < ph and crow[y] >= thr: y += 1
    y1 = y
    print(f"phone strip band: ({y0}, {y1})")

    slots = detect_slots(ppx, pw, max(0, y0-2), min(ph, y1+2))
    print(f"phone strip: {len(slots)} sprites, widths={[b-a for a,b in slots]}")

    phone_sprites = []
    for x0, x1 in slots:
        crop = phone_strip.crop((max(0,x0-2), max(0,y0-2), min(pw,x1+2), min(ph,y1+2)))
        phone_sprites.append(tight_crop(crop))

    need = 6
    if len(phone_sprites) < need and phone_sprites:
        phone_sprites += [phone_sprites[-1]] * (need - len(phone_sprites))
    phone_sprites = phone_sprites[:need]

    for col in range(8):
        atlas.paste(Image.new("RGBA", (CELL_W, CELL_H), (0,0,0,0)), (col*CELL_W, 7*CELL_H))
    for col, sp in enumerate(phone_sprites):
        cell = fit_into_cell(sp)
        atlas.alpha_composite(cell, (col*CELL_W, 7*CELL_H))
    print(f"patched row 7 with {len(phone_sprites)} phone sprites")

    atlas.save(ATLAS_PATH)
    atlas.save(WEBP_PATH, "WEBP", quality=92, method=6)
    print(f"saved {ATLAS_PATH}")
    print(f"saved {WEBP_PATH}")


if __name__ == "__main__":
    main()

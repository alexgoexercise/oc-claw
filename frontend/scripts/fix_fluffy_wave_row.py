"""
Fix fluffy-cat waving row (row 3): remove the extra grounded right-front paw
so the cat has 4 paws total (3 on ground + 1 raised).

The source AI frames have all 4 legs on the floor plus a raised front paw.
We erase the grounded right-front paw pixels only, preserving the raised limb.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public/assets/custom/fluffy-cat/spritesheet.png"
OUT_DIRS = [
    ROOT / "public/assets/custom/fluffy-cat",
]

CELL_W, CELL_H = 192, 208
WAVE_ROW = 3
WAVE_FRAMES = 4

# Grounded right-front paw erase zone (viewer right / cat's left front on floor)
PAW_X0, PAW_X1 = 100, 170
PAW_Y0, PAW_Y1 = 154, 206
# Preserve raised limb connection near top-right of erase box
LIMB_KEEP_X = 134
LIMB_KEEP_Y = 166


def is_dark_paw(r: int, g: int, b: int, a: int) -> bool:
    return a > 50 and max(r, g, b) < 130


def should_erase_paw_pixel(r: int, g: int, b: int, a: int, x: int, y: int) -> bool:
    if a < 15:
        return False
    if x >= LIMB_KEEP_X and y < LIMB_KEEP_Y:
        return False
    # Bottom-right grounded paw: dark toes/pads and surrounding fur
    if y >= 156 and x >= 104:
        if is_dark_paw(r, g, b, a):
            return True
        if max(r, g, b) < 200:
            return True
    return False


def patch_belly_hole(out: Image.Image, src: Image.Image) -> None:
    """Fill transparent gaps with belly fur sampled from above."""
    px = out.load()
    src_px = src.load()
    w, h = out.size
    for y in range(PAW_Y0, PAW_Y1):
        for x in range(PAW_X0 + 4, PAW_X1 - 6):
            if px[x, y][3] > 10:
                continue
            # sample from chest above same x
            for sy in range(y - 8, max(95, y - 30), -1):
                sr, sg, sb, sa = src_px[x, sy]
                if sa > 80 and max(sr, sg, sb) > 150:
                    shade = 1.0 - (y - PAW_Y0) * 0.003
                    px[x, y] = (int(sr * shade), int(sg * shade), int(sb * shade), min(255, sa - 10))
                    break


def fix_wave_frame(wave: Image.Image) -> Image.Image:
    out = wave.copy()
    px = out.load()
    for y in range(PAW_Y0, PAW_Y1):
        for x in range(PAW_X0, PAW_X1):
            r, g, b, a = px[x, y]
            if should_erase_paw_pixel(r, g, b, a, x, y):
                px[x, y] = (0, 0, 0, 0)
    patch_belly_hole(out, wave)
    return out


def main() -> None:
    atlas = Image.open(SRC).convert("RGBA")
    out_atlas = atlas.copy()
    for col in range(WAVE_FRAMES):
        x0 = col * CELL_W
        y0 = WAVE_ROW * CELL_H
        wave = atlas.crop((x0, y0, x0 + CELL_W, y0 + CELL_H))
        fixed = fix_wave_frame(wave)
        out_atlas.paste(fixed, (x0, y0))
        print(f"fixed wave frame {col}")

    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_atlas.save(out_dir / "spritesheet.png")
        out_atlas.save(out_dir / "spritesheet.webp", "WEBP", quality=92, method=6)
        print("wrote", out_dir)


if __name__ == "__main__":
    main()

"""
Regenerate fluffy-cat wave row (row 3): fix wave0 paws, rebuild frames 1-3.

Wave0 gets a clean paw fix (remove extra grounded right-front paw). Frames 1-3
are rebuilt from that wave0 base, copying only face/eye animation from the
pre-fix grey spritesheet so paw count and orientation stay consistent.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public/assets/custom/fluffy-cat/spritesheet.png"
OUT_DIRS = [ROOT / "public/assets/custom/fluffy-cat"]

CELL_W, CELL_H = 192, 208
WAVE_ROW = 3

# Paw erase (from fix_fluffy_wave_row.py, dark pads only)
PAW_X0, PAW_X1 = 100, 170
PAW_Y0, PAW_Y1 = 154, 206
LIMB_KEEP_X, LIMB_KEEP_Y = 134, 166

# Protected zones when copying animation onto wave0
GROUND_PAW = (88, 192, 148, 208)
RAISED_PAW = (108, 192, 38, 148)

# Animation copy regions
WINK_EYE = (16, 100, 35, 100)


def is_dark_paw(r: int, g: int, b: int, a: int) -> bool:
    return a > 50 and max(r, g, b) < 130


def should_erase_paw(r: int, g: int, b: int, a: int, x: int, y: int) -> bool:
    if a < 15:
        return False
    if x >= LIMB_KEEP_X and y < LIMB_KEEP_Y:
        return False
    if y >= 156 and x >= 104:
        return is_dark_paw(r, g, b, a)
    return False


def in_zone(x: int, y: int, zone: tuple[int, int, int, int]) -> bool:
    x0, x1, y0, y1 = zone
    return x0 <= x < x1 and y0 <= y < y1


def keep_from_wave0(x: int, y: int) -> bool:
    return in_zone(x, y, GROUND_PAW) or in_zone(x, y, RAISED_PAW)


def fix_wave0_paws(frame: Image.Image) -> Image.Image:
    """Remove extra grounded paw; fill belly holes from chest fur."""
    out = frame.copy()
    px = out.load()
    for y in range(PAW_Y0, PAW_Y1):
        for x in range(PAW_X0, PAW_X1):
            r, g, b, a = px[x, y]
            if should_erase_paw(r, g, b, a, x, y):
                px[x, y] = (0, 0, 0, 0)

    belly = frame.crop((55, 120, 100, 160)).resize((60, 50), Image.Resampling.LANCZOS)
    bpx = belly.load()
    for y in range(50):
        for x in range(60):
            tx, ty = 102 + x, 152 + y
            if tx >= CELL_W or ty >= CELL_H:
                continue
            if px[tx, ty][3] < 20:
                br, bg, bb, ba = bpx[x, y]
                if ba > 20:
                    px[tx, ty] = (br, bg, bb, min(ba, 220))
    return out


def copy_region(out: Image.Image, src: Image.Image, zone: tuple[int, int, int, int]) -> None:
    x0, x1, y0, y1 = zone
    out_px = out.load()
    src_px = src.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if keep_from_wave0(x, y):
                continue
            sr, sg, sb, sa = src_px[x, y]
            if sa > 20:
                out_px[x, y] = (sr, sg, sb, sa)


def load_pre_fix_atlas() -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    with open(tmp_path, "wb") as f:
        subprocess.run(
            ["git", "show", "cba6dd4:frontend/public/assets/custom/fluffy-cat/spritesheet.png"],
            cwd=ROOT.parent,
            stdout=f,
            check=True,
        )
    atlas = Image.open(tmp_path).convert("RGBA")
    tmp_path.unlink(missing_ok=True)
    return atlas


def crop_wave(atlas: Image.Image, col: int) -> Image.Image:
    x0 = col * CELL_W
    y0 = WAVE_ROW * CELL_H
    return atlas.crop((x0, y0, x0 + CELL_W, y0 + CELL_H))


def build_wave_row(pre_fix: Image.Image) -> list[Image.Image]:
    ref0 = crop_wave(pre_fix, 0)
    wave0 = fix_wave0_paws(ref0)

    # Frame 1 matches wave0 (hold pose); only frames 2-3 add the wink.
    w2 = wave0.copy()
    copy_region(w2, crop_wave(pre_fix, 2), WINK_EYE)

    return [wave0, wave0.copy(), w2, w2.copy()]


def main() -> None:
    pre_fix = load_pre_fix_atlas()
    current = Image.open(SRC).convert("RGBA")
    out_atlas = current.copy()

    frames = build_wave_row(pre_fix)
    y0 = WAVE_ROW * CELL_H
    for col, frame in enumerate(frames):
        out_atlas.paste(frame, (col * CELL_W, y0))
        print(f"built wave frame {col}")

    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_atlas.save(out_dir / "spritesheet.png")
        out_atlas.save(out_dir / "spritesheet.webp", "WEBP", quality=92, method=6)
        print("wrote", out_dir)


if __name__ == "__main__":
    main()

"""
combine_plots.py - stitch every run PNG in the output folder into ONE validation sheet.

Purpose: after a run + plot.bat, upload a single image instead of 15. The script
auto-discovers all *.png in the folder, so new plots are picked up with no edits here.

It is FAIL-LOUD: if it finds no PNGs (or the folder is missing) it errors instead of
silently producing an empty sheet.

Usage:
    py Scripts/combine_plots.py
    py Scripts/combine_plots.py --run-id 1
    py Scripts/combine_plots.py --folder output --cols 3 --tile-width 1000
    py Scripts/combine_plots.py --output output/validation_run1.png

Defaults:
    --folder       output            (where plot.bat writes PNGs)
    --run          auto-detect       (highest run<N> token found in filenames; else all)
    --cols         3                 (fewer cols = bigger, more legible tiles)
    --tile-width   1000              (px each plot is scaled to, aspect preserved)
    --output       <folder>/validation_run<N>.png

Notes:
- Only *.png is globbed, so .html / .csv / .txt are skipped automatically.
- The output file (and anything starting with 'validation_') is excluded from its own
  inputs, so re-running never nests the sheet inside itself.
- Tiles keep their native aspect ratio; each grid row is as tall as its tallest tile.
"""

import argparse
import os
import re
import sys
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

# ---- layout constants ------------------------------------------------------
MARGIN = 24          # outer border, px
GAP = 18             # space between tiles, px
LABEL_PAD = 8        # padding around the filename label, px
BG = (255, 255, 255)         # sheet background (matches matplotlib white)
LABEL_BG = (238, 238, 238)   # light strip behind each filename
LABEL_FG = (20, 20, 20)      # label text color
TITLE_FG = (0, 0, 0)
RUN_TOKEN = re.compile(r"run(\d+)", re.IGNORECASE)


def load_font(size):
    """Best-effort TrueType so labels are legible; fall back to bundled default."""
    candidates = [
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def detect_run(pngs):
    """Pick the highest run<N> present in the filenames, or None if no run tokens."""
    runs = set()
    for p in pngs:
        m = RUN_TOKEN.search(p.name)
        if m:
            runs.add(int(m.group(1)))
    return max(runs) if runs else None


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]

def main():
    print(f"Running: {os.path.basename(__file__)}")
    ap = argparse.ArgumentParser(description="Combine run PNGs into one validation sheet.")
    ap.add_argument("--folder", default="output", help="folder containing the PNGs")
    ap.add_argument("--run-id", "--run", dest="run", type=int, default=None,
                    help="only include files containing run<N> (default: auto-detect)")
    ap.add_argument("--cols", type=int, default=3, help="number of columns")
    ap.add_argument("--tile-width", type=int, default=1000,
                    help="px width each plot is scaled to (aspect preserved)")
    ap.add_argument("--output", default=None, help="output PNG path")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"ERROR: folder not found: {folder.resolve()}")

    # Discover PNGs (case-insensitive), excluding any prior validation sheet.
    pngs = sorted(
        p for p in folder.iterdir()
        if p.suffix.lower() == ".png" and not p.name.lower().startswith("validation_")
    )
    if not pngs:
        sys.exit(f"ERROR: no PNGs found in {folder.resolve()}")

    # Resolve the run filter.
    run = args.run if args.run is not None else detect_run(pngs)
    if run is not None:
        token = f"run{run}"
        selected = [p for p in pngs if token in p.name.lower()]
        if not selected:
            sys.exit(f"ERROR: no PNGs matching '{token}' in {folder.resolve()}")
        pngs = selected
        run_label = f"run{run}"
    else:
        run_label = "all"

    default_run = run if run is not None else 0
    out_path = Path(args.output) if args.output else folder / f"validation_run{default_run}.png"
    # Belt-and-suspenders: never let the output be one of its own inputs.
    pngs = [p for p in pngs if p.resolve() != out_path.resolve()]
    if not pngs:
        sys.exit("ERROR: nothing left to combine after excluding the output file")

    print(f"Combining {len(pngs)} PNG(s) [{run_label}] from {folder.resolve()}:")
    for p in pngs:
        print(f"  - {p.name}")

    title_font = load_font(34)
    label_font = load_font(22)

    # Scale every image to the tile width, preserving aspect ratio.
    tiles = []  # (name, scaled_image)
    for p in pngs:
        try:
            img = Image.open(p).convert("RGB")
        except Exception as e:  # noqa: BLE001 - report and skip unreadable files loudly
            print(f"  WARNING: could not open {p.name}: {e}")
            continue
        scale = args.tile_width / img.width
        new_size = (args.tile_width, max(1, round(img.height * scale)))
        tiles.append((p.name, img.resize(new_size, Image.LANCZOS)))

    if not tiles:
        sys.exit("ERROR: no readable images to combine")

    cols = max(1, args.cols)
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]

    # Measure a label strip height from the font.
    probe = Image.new("RGB", (10, 10))
    pdraw = ImageDraw.Draw(probe)
    _, lh = text_size(pdraw, "Ag", label_font)
    label_h = lh + 2 * LABEL_PAD
    _, th = text_size(pdraw, "Ag", title_font)
    title_h = th + 2 * LABEL_PAD

    # Canvas dimensions.
    canvas_w = MARGIN * 2 + cols * args.tile_width + (cols - 1) * GAP
    row_heights = [label_h + max(img.height for _, img in row) for row in rows]
    canvas_h = (MARGIN * 2 + title_h + GAP
                + sum(row_heights) + GAP * (len(rows) - 1))

    sheet = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(sheet)

    # Title.
    title = f"Rip validation  -  {run_label}  -  {len(tiles)} plots"
    draw.text((MARGIN, MARGIN), title, fill=TITLE_FG, font=title_font)

    # Lay out tiles.
    y = MARGIN + title_h + GAP
    for row, rh in zip(rows, row_heights):
        x = MARGIN
        for name, img in row:
            # label strip
            draw.rectangle([x, y, x + args.tile_width, y + label_h], fill=LABEL_BG)
            draw.text((x + LABEL_PAD, y + LABEL_PAD), name, fill=LABEL_FG, font=label_font)
            # image directly below the label
            sheet.paste(img, (x, y + label_h))
            x += args.tile_width + GAP
        y += rh + GAP

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    file_path = out_path.resolve()
    subprocess.run(["oxipng", "-o", "6", str(file_path)], check=True)

    print(f"Wrote {file_path}  ({sheet.width} x {sheet.height} px)")

if __name__ == "__main__":
    main()
"""
Tier 0 lensing diagnostic.

Projects the dark-matter dimple and the baryonic matter to 2D surface density
(sum along depth ~ a convergence-kappa proxy) and asks the dark-matter question
directly: is the gravitating dimple co-located with the baryons, offset from
them, or a diffuse fog?

Three panels:
  1. Baryon surface density  (what a telescope would see)
  2. Dimple surface density   (the lensing excess) with baryon contours overlaid
  3. Lensing-candidate cells  (explicit "mass where there is no matter")

Two scalars to track across the Tier 0 -> Tier 1 transition:
  - Pearson r(dimple, baryon): ~+1 co-located, ~0 diffuse fog, <0 anti-located
  - centroid offset (cells): displacement between the two surface-density centroids

Usage: py plot_lensing.py --run-id 1 [--timestep N]   (default: last timestep)
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def resolve_timestep(conn, run_id, requested):
    if requested is not None:
        return int(requested)
    row = conn.execute(
        "SELECT MAX(timestep) FROM cell WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None or row[0] is None:
        raise SystemExit(f"No cell data for run_id={run_id}")
    return int(row[0])


def load(conn, run_id, timestep):
    df_cols = ["col", "row", "matter_density", "rip_dimple", "is_lensing_candidate"]
    rows = conn.execute(
        """
        SELECT cp.col, cp.row, c.matter_density, c.rip_dimple, c.is_lensing_candidate
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ? AND c.is_black_hole = 0
        """,
        (run_id, timestep),
    ).fetchall()
    if not rows:
        raise SystemExit(f"No non-BH cells for run_id={run_id} timestep={timestep}")
    return np.array(rows, dtype=float), df_cols


def project_sum(data, cols, field):
    ci = cols.index("col")
    ri = cols.index("row")
    fi = cols.index(field)
    n_col = int(data[:, ci].max()) + 1
    n_row = int(data[:, ri].max()) + 1
    grid = np.zeros((n_row, n_col))
    np.add.at(grid, (data[:, ri].astype(int), data[:, ci].astype(int)), data[:, fi])
    return grid


def centroid(grid):
    total = grid.sum()
    if total <= 0:
        return None
    rr, cc = np.indices(grid.shape)
    return np.array([(rr * grid).sum() / total, (cc * grid).sum() / total])


def pearson(a, b):
    a = a.ravel()
    b = b.ravel()
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def lognorm(grid):
    pos = grid[grid > 0]
    if pos.size == 0:
        return mcolors.Normalize()
    return mcolors.LogNorm(vmin=max(pos.min(), pos.max() * 1e-6), vmax=pos.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=1)
    ap.add_argument("--timestep", type=int, default=None)
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    ts = resolve_timestep(conn, args.run_id, args.timestep)
    data, cols = load(conn, args.run_id, ts)
    conn.close()

    baryon = project_sum(data, cols, "matter_density")
    dimple = project_sum(data, cols, "rip_dimple")
    lens = project_sum(data, cols, "is_lensing_candidate")  # count of flagged cells per column

    r = pearson(dimple, baryon)
    cb = centroid(baryon)
    cd = centroid(dimple)
    offset = float(np.linalg.norm(cd - cb)) if (cb is not None and cd is not None) else float("nan")
    n_lens = int(data[:, cols.index("is_lensing_candidate")].sum())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(19, 6))
    fig.suptitle(
        f"Lensing diagnostic — Run {args.run_id}, timestep {ts}    "
        f"r(dimple,baryon)={r:+.3f}   centroid offset={offset:.2f} cells   "
        f"lensing cells={n_lens}",
        fontsize=12,
    )

    im0 = axes[0].imshow(baryon, origin="lower", cmap="inferno", norm=lognorm(baryon), aspect="auto")
    axes[0].set_title("Baryon surface density (visible)")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(dimple, origin="lower", cmap="magma", norm=lognorm(dimple), aspect="auto")
    axes[1].set_title("Dimple surface density (lensing excess)\nwhite contours = baryons")
    if baryon.max() > 0:
        axes[1].contour(baryon, levels=4, colors="white", linewidths=0.5, alpha=0.6)
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    im2 = axes[2].imshow(lens, origin="lower", cmap="cividis", aspect="auto")
    axes[2].set_title("Lensing candidates\n(dark matter where baryons are sparse)")
    plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)

    for ax in axes:
        ax.set_xlabel("Col")
        ax.set_ylabel("Row")

    plt.tight_layout()
    out = OUTPUT_DIR / f"lensing_run{args.run_id}_t{ts}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"r(dimple,baryon)={r:+.4f}  centroid_offset={offset:.3f} cells  lensing_cells={n_lens}")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
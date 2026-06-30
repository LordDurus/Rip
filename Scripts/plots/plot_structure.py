import argparse
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import shutil
import subprocess
from pathlib import Path
from scipy.ndimage import label

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"
OUTPUT_DIR = REPO / "output"


def save_png(path):
    if shutil.which("optipng.exe"):
        try:
            subprocess.run(["optipng.exe", "-o7", str(path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


def find_matter_peak(conn, run_id):
    """Find the timestep where total_matter peaked."""
    df = pd.read_sql_query(
        "SELECT timestep FROM timestep_summary WHERE run_id = ? ORDER BY total_matter DESC LIMIT 1",
        conn, params=(run_id,)
    )
    if df.empty:
        return None
    return int(df["timestep"].iloc[0])


def load_grid(conn, run_id, timestep, grid_size):
    """Load matter density and black hole status into a 3D numpy grid."""
    df = pd.read_sql_query(
        """
        SELECT cp.col, cp.row, c.layer, c.matter_density, c.is_black_hole
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ?
        """,
        conn, params=(int(run_id), int(timestep))
    )
    if df.empty:
        return None, None

    density = np.zeros((grid_size, grid_size, grid_size))
    is_bh = np.zeros((grid_size, grid_size, grid_size), dtype=bool)

    for _, row in df.iterrows():
        c, r, l = int(row["col"]), int(row["row"]), int(row["layer"])
        if c < grid_size and r < grid_size and l < grid_size:
            if row["is_black_hole"]:
                is_bh[r, c, l] = True
                density[r, c, l] = np.nan
            else:
                density[r, c, l] = row["matter_density"]

    return density, is_bh


def classify_structure(density, filament_percentile=70, void_percentile=30):
    """
    Classify cells into filament, void, or sheet based on density percentiles.
    Returns an integer grid: 2=filament, 1=sheet, 0=void, -1=black hole (nan)
    """
    valid = density[~np.isnan(density)]
    filament_thresh = np.percentile(valid, filament_percentile)
    void_thresh = np.percentile(valid, void_percentile)

    structure = np.ones(density.shape, dtype=int)  # default: sheet
    structure[density >= filament_thresh] = 2       # filament
    structure[density <= void_thresh] = 0           # void
    structure[np.isnan(density)] = -1               # black hole

    return structure, filament_thresh, void_thresh


def connected_components(structure, target_class):
    """Count and size connected components for a given structure class."""
    binary = (structure == target_class)
    labeled, num_features = label(binary)
    sizes = [int((labeled == i).sum()) for i in range(1, num_features + 1)]
    return num_features, sizes


def project_2d(density):
    """Project 3D density grid to 2D by taking the max density along depth axis."""
    return np.nanmax(density, axis=2)


def main():
    parser = argparse.ArgumentParser(description="Filament and void structure analysis.")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--timestep", type=int, default=None,
                        help="Timestep to analyze (default: matter density peak)")
    parser.add_argument("--grid-size", type=int, default=64)
    parser.add_argument("--filament-percentile", type=float, default=70,
                        help="Density percentile above which cells are filaments (default: 70)")
    parser.add_argument("--void-percentile", type=float, default=30,
                        help="Density percentile below which cells are voids (default: 30)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    if args.run_id is not None:
        run_id = args.run_id
    else:
        runs = pd.read_sql_query(
            "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1", conn)
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = int(runs["run_id"].iloc[0])

    if args.timestep is not None:
        timestep = args.timestep
        print(f"Using requested timestep {timestep}")
    else:
        timestep = find_matter_peak(conn, run_id)
        if timestep is None:
            print("Could not find matter peak; defaulting to timestep 0.")
            timestep = 0
        else:
            print(f"Using matter density peak at timestep {timestep}")

    print(f"Run {run_id}, timestep {timestep}, grid {args.grid_size}³")

    density, is_bh = load_grid(conn, run_id, timestep, args.grid_size)
    conn.close()

    if density is None:
        print("No data found.")
        return

    structure, filament_thresh, void_thresh = classify_structure(
        density, args.filament_percentile, args.void_percentile)

    # Connected component statistics
    n_filaments, filament_sizes = connected_components(structure, 2)
    n_voids, void_sizes = connected_components(structure, 0)

    total_cells = args.grid_size ** 3
    bh_count = int(is_bh.sum())
    filament_cells = int((structure == 2).sum())
    void_cells = int((structure == 0).sum())
    sheet_cells = int((structure == 1).sum())

    print("\n--- Structure Statistics ---")
    print(f"Black holes:      {bh_count:>8} ({100*bh_count/total_cells:.1f}%)")
    print(f"Filament cells:   {filament_cells:>8} ({100*filament_cells/total_cells:.1f}%)")
    print(f"Sheet cells:      {sheet_cells:>8} ({100*sheet_cells/total_cells:.1f}%)")
    print(f"Void cells:       {void_cells:>8} ({100*void_cells/total_cells:.1f}%)")
    print(f"Filament thresh:  {filament_thresh:.4f}")
    print(f"Void thresh:      {void_thresh:.4f}")
    print(f"Distinct filament regions: {n_filaments}")
    print(f"Distinct void regions:     {n_voids}")
    if filament_sizes:
        print(f"Largest filament: {max(filament_sizes)} cells")
    if void_sizes:
        print(f"Largest void:     {max(void_sizes)} cells")
   
    # Plot
    # 2D projection
    proj = project_2d(density)

    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(f"Large-Scale Structure — Run {run_id}, timestep {timestep}", fontsize=13)

    # Left: density projection
    im = axes[0].imshow(proj, cmap="plasma", origin="lower", aspect="auto")
    plt.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04, label="Matter density (max projection)")
    axes[0].set_title("Matter Density (2D projection)")
    axes[0].set_xlabel("Col")
    axes[0].set_ylabel("Row")
    
    # Right: density histogram with threshold lines
    valid_density = density[~np.isnan(density)].ravel()
    axes[1].hist(valid_density, bins=80, color="steelblue", alpha=0.7, edgecolor="none")
    axes[1].axvline(filament_thresh, color="red", linestyle="--",
                    label=f"Filament threshold ({filament_thresh:.3f})")
    axes[1].axvline(void_thresh, color="navy", linestyle="--",
                    label=f"Void threshold ({void_thresh:.3f})")
    axes[1].set_xlabel("Matter Density")
    axes[1].set_ylabel("Cell Count")
    axes[1].set_title("Density Distribution with Thresholds")
    axes[1].legend(fontsize=9)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"structure_run{run_id}_t{timestep}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    save_png(out_path)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
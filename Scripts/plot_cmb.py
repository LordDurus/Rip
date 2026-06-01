import argparse
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import shutil
import subprocess
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

FIELDS = [
    ("matter_density", "Matter Density",      "inferno"),
    ("rip_strength",   "Rip Field Strength",   "plasma"),
    ("dimple_strength","Dimple Strength",       "viridis"),
]


def load_last_timestep(conn, run_id):
    """Load all cell data for the final timestep of a given run."""
    max_timestep_df = pd.read_sql_query(
        "SELECT MAX(timestep) as max_t FROM cell WHERE run_id = ?",
        conn, params=(run_id,)
    )
    print(f"  max_timestep query returned {len(max_timestep_df)} rows")

    max_timestep = max_timestep_df['max_t'].iloc[0]
    print(f"  max_timestep = {max_timestep}")

    if max_timestep is None:
        print(f"  No cell data found for run_id={run_id}")
        return pd.DataFrame(), None

    df = pd.read_sql_query(
        """
        SELECT
            cp.col, cp.row, c.layer,
            c.matter_density, c.rip_strength, c.dimple_strength,
            c.is_black_hole, c.curvature
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ?
        """,
        conn, params=(int(run_id), int(max_timestep))
    )
    print(f"  cell JOIN query returned {len(df)} rows")
    return df, max_timestep


def project_2d(df, field, agg="mean"):
    """
    Flatten the 3D grid to a 2D image by averaging (or summing) along the depth axis.
    Returns a 2D numpy array (rows x cols).
    """
    pivot = df.groupby(["row", "col"])[field].agg(agg).reset_index()
    rows = sorted(pivot["row"].unique())
    cols = sorted(pivot["col"].unique())
    grid = np.full((len(rows), len(cols)), np.nan)

    row_idx = {r: i for i, r in enumerate(rows)}
    col_idx = {c: i for i, c in enumerate(cols)}

    for _, entry in pivot.iterrows():
        grid[row_idx[entry["row"]], col_idx[entry["col"]]] = entry[field]

    return grid


def plot_field(ax, grid, title, cmap, black_hole_mask=None):
    """Plot a single 2D field with optional black hole overlay."""
    vmin = np.nanmin(grid)
    vmax = np.nanmax(grid)

    if vmax > 0 and (vmax / max(vmin, 1e-10)) > 1000:
        norm = mcolors.LogNorm(vmin=max(vmin, 1e-10), vmax=vmax)
    else:
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    im = ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", aspect="auto",
                   interpolation="nearest")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    if black_hole_mask is not None:
        bh_rows, bh_cols = np.nonzero(black_hole_mask)
        if len(bh_rows) > 0:
            ax.scatter(bh_cols, bh_rows, c="white", s=2, alpha=0.6,
                       label=f"{len(bh_rows)} black holes")
            ax.legend(loc="upper right", fontsize=7, framealpha=0.5)

    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Col")
    ax.set_ylabel("Row")


def save_png(path):
    if shutil.which("optipng.exe"):
        try:
            subprocess.run(["optipng.exe", "-o7", str(path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


def main():
    parser = argparse.ArgumentParser(description="Plot CMB-style projections for a simulation run.")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID to plot (default: most recent completed run)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    if args.run_id is not None:
        runs = pd.read_sql_query(
            "SELECT run_id, status FROM run WHERE run_id = ?",
            conn, params=(args.run_id,)
        )
        print(f"Run query returned {len(runs)} rows")
        if runs.empty:
            print(f"Run ID {args.run_id} not found.")
            conn.close()
            return
        run_id = args.run_id
        print(f"Plotting requested run_id={run_id} (status: {runs['status'].iloc[0]})")
    else:
        runs = pd.read_sql_query(
            "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1",
            conn
        )
        print(f"Completed runs query returned {len(runs)} rows")
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = runs["run_id"].iloc[0]
        print(f"Plotting most recent completed run_id={run_id}")

    df, max_timestep = load_last_timestep(conn, run_id)
    conn.close()

    if df.empty:
        print("No cell data found.")
        return

    print(f"Loaded {len(df)} cells at timestep {max_timestep}.")
    print(f"Black holes: {df['is_black_hole'].sum()}")

    # Build black hole mask (projected — True if any layer in that col/row is a BH)
    bh_proj = df.groupby(["row", "col"])["is_black_hole"].max().reset_index()
    rows = sorted(df["row"].unique())
    cols = sorted(df["col"].unique())
    row_idx = {r: i for i, r in enumerate(rows)}
    col_idx = {c: i for i, c in enumerate(cols)}
    bh_mask = np.zeros((len(rows), len(cols)), dtype=bool)
    for _, entry in bh_proj.iterrows():
        bh_mask[row_idx[entry["row"]], col_idx[entry["col"]]] = bool(entry["is_black_hole"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Combined figure: all 3 fields side by side ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"CMB-style Projection — Run {run_id}, Timestep {max_timestep}", fontsize=13)

    for ax, (field, label, cmap) in zip(axes, FIELDS):
        grid = project_2d(df, field)
        plot_field(ax, grid, label, cmap, black_hole_mask=bh_mask)

    plt.tight_layout()
    combined_path = OUTPUT_DIR / f"cmb_combined_run{run_id}.png"
    plt.savefig(combined_path, dpi=300)
    plt.close()
    save_png(combined_path)
    print(f"Saved: {combined_path}")

    # --- Individual figures ---
    for field, label, cmap in FIELDS:
        fig, ax = plt.subplots(figsize=(8, 7))
        grid = project_2d(df, field)
        plot_field(ax, grid, f"{label}\nRun {run_id}, Timestep {max_timestep}", cmap,
                   black_hole_mask=bh_mask)
        plt.tight_layout()
        out_path = OUTPUT_DIR / f"cmb_{field}_run{run_id}.png"
        plt.savefig(out_path, dpi=300)
        plt.close()
        save_png(out_path)
        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
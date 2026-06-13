import argparse
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import shutil
import subprocess
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# Field to treat as the CMB analog. matter_density, rip_strength, or curvature.
DEFAULT_FIELD = "rip_strength"


def save_png(path):
    if shutil.which("optipng.exe"):
        try:
            subprocess.run(["optipng.exe", "-o7", str(path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


def find_inflation_end(conn, run_id):
    """
    Find the timestep where inflation ended: the last timestep where the
    growth rate d(ln a)/dt was still meaningfully above zero.
    """
    df = pd.read_sql_query(
        "SELECT timestep, time_myr, scale_factor FROM timestep_summary WHERE run_id = ? ORDER BY timestep",
        conn, params=(run_id,)
    )
    if df.empty:
        return None

    scale = df["scale_factor"].values
    time = df["time_myr"].values
    ln_a = np.log(scale)
    growth = np.gradient(ln_a, time)

    peak = growth.max()
    threshold = 0.05 * peak
    inflating = growth > threshold
    if not inflating.any():
        return None

    stop_idx = len(inflating) - 1 - np.argmax(inflating[::-1])
    return int(df["timestep"].iloc[stop_idx])


def load_field_grid(conn, run_id, timestep, field):
    """Load a single field as a 2D grid, averaged along the depth/layer axis."""
    df = pd.read_sql_query(
        f"""
        SELECT cp.col, cp.row, c.{field}, c.is_black_hole
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ?
        """,
        conn, params=(int(run_id), int(timestep))
    )
    if df.empty:
        return None

    # Exclude black hole cells — their sentinel value (1e30) drowns out real density signal
    df = df[df["is_black_hole"] == 0]

    pivot = df.groupby(["row", "col"])[field].mean().reset_index()
    rows = sorted(pivot["row"].unique())
    cols = sorted(pivot["col"].unique())
    grid = np.full((len(rows), len(cols)), np.nan)
    row_idx = {r: i for i, r in enumerate(rows)}
    col_idx = {c: i for i, c in enumerate(cols)}
    for _, e in pivot.iterrows():
        grid[row_idx[e["row"]], col_idx[e["col"]]] = e[field]

    # NaNs here now mean the col/row had ONLY black hole cells at all depths
    # Fill with the non-BH mean so the FFT doesn't break
    if np.isnan(grid).any():
        grid[np.isnan(grid)] = np.nanmean(grid)
    return grid


def radial_power_spectrum(field2d):
    """
    Compute the radially-averaged power spectrum of a 2D field.
    Returns (k, power) where k is spatial frequency (analog of multipole l)
    and power is the average squared amplitude at that scale.
    """
    # Work with fluctuations: subtract the mean so we measure variation, not the DC level
    fluct = field2d - np.mean(field2d)

    # 2D FFT, shift zero-frequency to center, take power
    f = np.fft.fft2(fluct)
    f = np.fft.fftshift(f)
    power2d = np.abs(f) ** 2

    ny, nx = power2d.shape
    cy, cx = ny // 2, nx // 2

    # Radial distance of each pixel from center = spatial frequency magnitude
    y, x = np.indices(power2d.shape)
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    r = r.astype(int)

    # Average power in each integer-radius annulus
    tbin = np.bincount(r.ravel(), power2d.ravel())
    nr = np.bincount(r.ravel())
    radial_power = tbin / np.maximum(nr, 1)

    k = np.arange(len(radial_power))
    # Drop k=0 (the mean, already removed) and the highest frequencies (noise)
    return k[1:nx // 2], radial_power[1:nx // 2]


def main():
    parser = argparse.ArgumentParser(description="CMB-analog power spectrum from the field right after inflation.")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID (default: most recent completed run)")
    parser.add_argument("--field", type=str, default=DEFAULT_FIELD,
                        choices=["rip_strength", "matter_density", "curvature"],
                        help=f"Field to analyze (default: {DEFAULT_FIELD})")
    parser.add_argument("--timestep", type=int, default=None,
                        help="Timestep to analyze (default: auto-detect end of inflation)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    if args.run_id is not None:
        runs = pd.read_sql_query("SELECT run_id FROM run WHERE run_id = ?", conn, params=(args.run_id,))
        if runs.empty:
            print(f"Run ID {args.run_id} not found.")
            conn.close()
            return
        run_id = int(args.run_id)
    else:
        runs = pd.read_sql_query(
            "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1", conn)
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = int(runs["run_id"].iloc[0])

    # Determine timestep
    if args.timestep is not None:
        timestep = int(args.timestep)
        print(f"Using requested timestep {timestep}")
    else:
        timestep = find_inflation_end(conn, run_id)
        if timestep is None:
            print("Could not detect inflation end; defaulting to timestep 0.")
            timestep = 0
        else:
            print(f"Detected end of inflation at timestep {timestep}")

    print(f"Run {run_id}, field '{args.field}', timestep {timestep}")

    grid = load_field_grid(conn, run_id, timestep, args.field)
    conn.close()

    if grid is None:
        print("No data found for that run/timestep.")
        return

    print(f"Field grid: {grid.shape}, mean={np.mean(grid):.4g}, std={np.std(grid):.4g}")

    k, power = radial_power_spectrum(grid)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle(f"CMB-analog Power Spectrum — Run {run_id}, '{args.field}' at timestep {timestep}", fontsize=13)

    # Left: the fluctuation map
    fluct = grid - np.mean(grid)
    im = ax1.imshow(fluct, cmap="RdBu_r", origin="lower", aspect="auto")
    plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04, label="fluctuation")
    ax1.set_title("Fluctuation Map (field − mean)")
    ax1.set_xlabel("Col")
    ax1.set_ylabel("Row")

    # Right: the radial power spectrum (the actual CMB test)
    ax2.loglog(k, power, color="tab:blue", lw=2, marker="o", markersize=3)
    ax2.set_xlabel("Spatial frequency k  (analog of multipole l)")
    ax2.set_ylabel("Power P(k)")
    ax2.set_title("Radially-Averaged Power Spectrum")
    ax2.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"cmb_power_run{run_id}_{args.field}_t{timestep}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    save_png(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
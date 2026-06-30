BLUE_TAB = "tab:blue"

import argparse
import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import shutil
import subprocess
from pathlib import Path

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


def main():
    print(f"Running: {os.path.basename(__file__)}")
    parser = argparse.ArgumentParser(description="Plot inflation (scale factor and growth rate) for a simulation run.")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID to plot (default: most recent completed run)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    if args.run_id is not None:
        runs = pd.read_sql_query("SELECT run_id, status FROM run WHERE run_id = ?", conn, params=(args.run_id,))
        if runs.empty:
            print(f"Run ID {args.run_id} not found.")
            conn.close()
            return
        run_id = int(args.run_id)
        print(f"Plotting requested run_id={run_id} (status: {runs['status'].iloc[0]})")
    else:
        runs = pd.read_sql_query(
            "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1", conn
        )
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = int(runs["run_id"].iloc[0])
        print(f"Plotting most recent completed run_id={run_id}")

    df = pd.read_sql_query(
        """
        SELECT timestep, time_myr, scale_factor
        FROM timestep_summary
        WHERE run_id = ?
        ORDER BY timestep
        """,
        conn, params=(run_id,)
    )
    conn.close()

    if df.empty:
        print("No timestep_summary data found.")
        return

    print(f"Loaded {len(df)} timesteps.")

    time = df["time_myr"].values
    scale = df["scale_factor"].values

    # Growth rate: d(ln a)/dt — the inflation signature.
    # High during inflation, drops toward zero when expansion stops.
    ln_a = np.log(scale)
    growth_rate = np.gradient(ln_a, time)

    # Detect inflation window: where growth rate is above 5% of its peak
    peak = growth_rate.max()
    threshold = 0.05 * peak
    inflating = growth_rate > threshold
    if inflating.any():
        start_idx = np.argmax(inflating)
        stop_idx = len(inflating) - 1 - np.argmax(inflating[::-1])
        t_start = time[start_idx]
        t_stop = time[stop_idx]
        print(f"Inflation window: t={t_start:.3f} to t={t_stop:.3f} Myr")
    else:
        t_start = t_stop = None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), sharex=True)
    fig.suptitle(f"Inflation — Run {run_id}", fontsize=14)

    # --- Top: scale factor (log scale) ---
    ax1.semilogy(time, scale, color="darkorange", lw=2)
    ax1.set_ylabel("Scale Factor a (log)")
    ax1.set_title("Cosmic Expansion")
    ax1.grid(True, alpha=0.3)
    if t_start is not None:
        ax1.axvspan(t_start, t_stop, alpha=0.15, color=BLUE_TAB, label="Inflation epoch")
        ax1.legend(loc="lower right")

    # --- Bottom: growth rate ---
    ax2.plot(time, growth_rate, color=BLUE_TAB, lw=2)
    ax2.set_xlabel("Time (Myr)")
    ax2.set_ylabel("Growth Rate  d(ln a)/dt")
    ax2.set_title("Expansion Rate (inflation start/stop)")
    ax2.grid(True, alpha=0.3)
    if t_start is not None:
        ax2.axvspan(t_start, t_stop, alpha=0.15, color=BLUE_TAB)
        ax2.axvline(t_start, color="green", ls="--", lw=1, label=f"start (t={t_start:.2f})")
        ax2.axvline(t_stop, color="red", ls="--", lw=1, label=f"stop (t={t_stop:.2f})")
        ax2.legend(loc="upper right")

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"inflation_run{run_id}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    save_png(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
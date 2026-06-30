import argparse
import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
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


def load_summary(conn, run_id):
    return pd.read_sql_query(
        """
        SELECT timestep, scale_factor, total_matter
        FROM timestep_summary
        WHERE run_id = ?
        ORDER BY timestep ASC
        """,
        conn, params=(run_id,)
    )


def main():
    print(f"Running: {os.path.basename(__file__)}")
    parser = argparse.ArgumentParser(description="Plot total matter (non-BH) vs scale factor over time.")
    parser.add_argument("--run-id", type=int, default=None,
                        help="Run ID to plot (default: most recent completed run)")
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
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = int(runs["run_id"].iloc[0])
        print(f"Plotting most recent completed run_id={run_id}")

    df = load_summary(conn, run_id)
    conn.close()

    if df.empty:
        print("No timestep_summary data found.")
        return

    if df["total_matter"].isna().all():
        print("total_matter column is all NULL — has it been populated yet?")
        return

    print(f"Loaded {len(df)} timesteps.")
    print(f"total_matter range: {df['total_matter'].min():.4f} – {df['total_matter'].max():.4f}")
    print(f"scale_factor range: {df['scale_factor'].min():.4f} – {df['scale_factor'].max():.4f}")

    fig, ax1 = plt.subplots(figsize=(12, 6))
    fig.suptitle(f"Total Matter vs Scale Factor — Run {run_id}", fontsize=13)

    color_matter = "steelblue"
    color_scale = "tomato"

    ax1.set_xlabel("Timestep")
    ax1.set_ylabel("Total Matter (non-BH cells)", color=color_matter)
    ax1.plot(df["timestep"], df["total_matter"], color=color_matter, linewidth=1.5,
             label="Total Matter")
    ax1.tick_params(axis="y", labelcolor=color_matter)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Scale Factor a(t)", color=color_scale)
    ax2.plot(df["timestep"], df["scale_factor"], color=color_scale, linewidth=1.5,
             linestyle="--", label="Scale Factor")
    ax2.tick_params(axis="y", labelcolor=color_scale)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"matter_run{run_id}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    save_png(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
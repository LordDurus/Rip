import argparse
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import shutil
import subprocess
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def save_png(path):
    if shutil.which("optipng.exe"):
        try:
            subprocess.run(["optipng.exe", "-o7", str(path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


def find_max_timestep(conn, run_id):
    df = pd.read_sql_query(
        "SELECT MAX(timestep) AS t FROM cell WHERE run_id = ?",
        conn, params=(run_id,)
    )
    if df.empty or df["t"].iloc[0] is None:
        return None
    return int(df["t"].iloc[0])


def load_smbh(conn, run_id, timestep):
    return pd.read_sql_query(
        """
        SELECT matter_density, smbh_connection_strength, curvature
        FROM cell
        WHERE run_id = ? AND timestep = ? AND is_supermassive = 1
        """,
        conn, params=(int(run_id), int(timestep))
    )


def main():
    parser = argparse.ArgumentParser(
        description="SMBH mass distribution and connection-strength relationship.")
    parser.add_argument("--run-id", type=int, default=None,
                        help="Run ID to plot (default: most recent completed run)")
    parser.add_argument("--timestep", type=int, default=None,
                        help="Timestep to plot (default: final timestep of the run)")
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
            "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1", conn)
        if runs.empty:
            print("No completed runs found.")
            conn.close()
            return
        run_id = int(runs["run_id"].iloc[0])
        print(f"Plotting most recent completed run_id={run_id}")

    timestep = args.timestep if args.timestep is not None else find_max_timestep(conn, run_id)
    if timestep is None:
        print("No cell data found for this run.")
        conn.close()
        return
    print(f"Using timestep {timestep}")

    df = load_smbh(conn, run_id, timestep)
    conn.close()

    if df.empty:
        print("No supermassive black holes found at this timestep.")
        return

    print(f"SMBH count: {len(df)}")
    print(f"Mass range:       {df['matter_density'].min():.3f} – {df['matter_density'].max():.1f}")
    print(f"Connection range: {df['smbh_connection_strength'].min():.3e} – {df['smbh_connection_strength'].max():.3e}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f"Supermassive Black Holes — Run {run_id}, timestep {timestep}", fontsize=13)

    # --- Left: mass distribution histogram (log x) ---
    mass = df["matter_density"].clip(lower=1e-3)
    log_bins = np.logspace(np.log10(mass.min()), np.log10(mass.max()), 50)
    ax1.hist(mass, bins=log_bins, color="steelblue", alpha=0.8, edgecolor="none")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("SMBH Mass (matter_density)")
    ax1.set_ylabel("Count")
    ax1.set_title(f"Mass Distribution ({len(df)} SMBHs)")
    ax1.axvline(df["matter_density"].median(), color="tomato", linestyle="--",
                label=f"median {df['matter_density'].median():.1f}")
    ax1.legend(fontsize=9)

    # --- Right: connection strength vs mass, colored by curvature ---
    conn_strength = df["smbh_connection_strength"].clip(lower=1e-30)
    sc = ax2.scatter(conn_strength, mass, c=df["curvature"], cmap="viridis",
                     s=10, alpha=0.5, edgecolors="none")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("Connection Strength")
    ax2.set_ylabel("SMBH Mass (matter_density)")
    ax2.set_title("Connection Strength vs Mass\n(color = formation curvature)")
    plt.colorbar(sc, ax=ax2, label="curvature", fraction=0.046, pad=0.04)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"smbh_run{run_id}_t{timestep}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    save_png(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
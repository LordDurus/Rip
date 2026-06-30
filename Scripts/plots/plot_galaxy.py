import argparse
import os
import sqlite3
import pandas as pd
import numpy as np
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

# Grid is 64^3; centroids live in [0, 64). Fix axes so the two panels share scale.
GRID_SIZE = 64


def save_png(path):
    if shutil.which("optipng.exe"):
        try:
            subprocess.run(["optipng.exe", "-o7", str(path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


def resolve_run_id(conn, run_id):
    if run_id is not None:
        runs = pd.read_sql_query(
            "SELECT run_id, status FROM run WHERE run_id = ?", conn, params=(run_id,))
        if runs.empty:
            print(f"Run ID {run_id} not found.")
            return None
        print(f"Plotting requested run_id={run_id} (status: {runs['status'].iloc[0]})")
        return run_id
    runs = pd.read_sql_query(
        "SELECT run_id FROM run WHERE status = 'completed' ORDER BY run_id DESC LIMIT 1", conn)
    if runs.empty:
        print("No completed runs found.")
        return None
    rid = int(runs.iloc[0]["run_id"])
    print(f"Plotting most recent completed run_id={rid}")
    return rid


def available_timesteps(conn, run_id):
    """Timesteps that actually have galaxy snapshots, via the galaxy join."""
    df = pd.read_sql_query(
        """
        SELECT DISTINCT gt.timestep
        FROM galaxy_timestep gt
        JOIN galaxy g ON g.galaxy_id = gt.galaxy_id
        WHERE g.run_id = ?
        ORDER BY gt.timestep ASC
        """,
        conn, params=(run_id,))
    return df["timestep"].to_numpy()


def load_galaxies_at(conn, run_id, timestep):
    """One row per galaxy active at `timestep`, with centroid, mass, SMBH count."""
    return pd.read_sql_query(
        """
        SELECT gt.galaxy_id, gt.centroid_col, gt.centroid_row,
               gt.total_mass, gt.smbh_count, gt.cell_count
        FROM galaxy_timestep gt
        JOIN galaxy g ON g.galaxy_id = gt.galaxy_id
        WHERE g.run_id = ? AND gt.timestep = ?
        """,
        conn, params=(run_id, timestep))


def pick_timesteps(steps, early_arg, late_arg):
    """Resolve requested early/late timesteps to the nearest available ones."""
    if len(steps) == 0:
        return None, None
    if early_arg is None:
        early = int(steps[0])
    else:
        early = int(steps[np.argmin(np.abs(steps - early_arg))])
    if late_arg is None:
        late = int(steps[-1])
    else:
        late = int(steps[np.argmin(np.abs(steps - late_arg))])
    return early, late


def mass_to_size(mass):
    """Map total_mass to a marker area. Log scale so a few massive galaxies
    don't swamp the rest; clamped to a readable range."""
    m = np.asarray(mass, dtype=float)
    m = np.where(m > 0, m, np.nan)
    sizes = 20.0 + 60.0 * (np.log10(m) - np.nanmin(np.log10(m)))
    return np.nan_to_num(sizes, nan=20.0)


def draw_panel(ax, df, timestep, vmin, vmax, smax):
    ax.set_title(f"timestep {timestep}  ({len(df)} galaxies)")
    ax.set_xlabel("Col")
    ax.set_ylabel("Row")
    ax.set_xlim(0, GRID_SIZE)
    ax.set_ylim(0, GRID_SIZE)
    ax.set_aspect("equal")
    if df.empty:
        ax.text(0.5, 0.5, "no galaxies", ha="center", va="center",
                transform=ax.transAxes, color="0.5")
        return None
    sizes = mass_to_size(df["total_mass"])
    sc = ax.scatter(
        df["centroid_col"], df["centroid_row"],
        s=sizes, c=df["smbh_count"],
        cmap="viridis", vmin=vmin, vmax=vmax,
        edgecolors="black", linewidths=0.4, alpha=0.85)
    return sc


def main():
    print(f"Running: {os.path.basename(__file__)}")
    parser = argparse.ArgumentParser(
        description="Galaxy centroid map (2D projection), early vs late timestep. "
                    "Marker size = total_mass, color = SMBH count.")
    parser.add_argument("--run-id", type=int, default=None,
                        help="Run ID to plot (default: most recent completed run)")
    parser.add_argument("--timestep", type=int, default=None,
                        help="Late-panel timestep (default: last with galaxies). "
                             "Matches the --timestep convention of the other plot scripts.")
    parser.add_argument("--early", type=int, default=None,
                        help="Early-panel timestep (default: first with galaxies)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    run_id = resolve_run_id(conn, args.run_id)
    if run_id is None:
        conn.close()
        return

    steps = available_timesteps(conn, run_id)
    if len(steps) == 0:
        print(f"No galaxy snapshots found for run {run_id}. "
              "Has galaxy persistence been wired and the run completed?")
        conn.close()
        return

    early, late = pick_timesteps(steps, args.early, args.timestep)
    df_early = load_galaxies_at(conn, run_id, early)
    df_late = load_galaxies_at(conn, run_id, late)
    conn.close()

    # Shared color scale across panels so SMBH-count colors are comparable.
    smbh_vals = pd.concat([df_early["smbh_count"], df_late["smbh_count"]])
    vmin = float(smbh_vals.min()) if not smbh_vals.empty else 0.0
    vmax = float(smbh_vals.max()) if not smbh_vals.empty else 1.0
    if vmin == vmax:
        vmax = vmin + 1.0

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.5))
    fig.suptitle(f"Galaxy Centroids — Run {run_id}", fontsize=15)

    draw_panel(axes[0], df_early, early, vmin, vmax, None)
    sc = draw_panel(axes[1], df_late, late, vmin, vmax, None)

    # Colorbar driven by whichever panel has data.
    mappable = sc
    if mappable is None:
        # early panel may have data if late was empty
        for ax in axes:
            for coll in ax.collections:
                mappable = coll
                break
            if mappable is not None:
                break
    if mappable is not None:
        cbar = fig.colorbar(mappable, ax=axes, fraction=0.046, pad=0.04)
        cbar.set_label("SMBH count")

    # Legend explaining marker size (mass) with a couple of reference sizes.
    note = ("Marker size \u221d log\u2081\u2080(total_mass);  "
            "color = SMBH count per galaxy")
    fig.text(0.5, 0.02, note, ha="center", fontsize=10, color="0.3")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"galaxy_run{run_id}.png"
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    save_png(out_path)
    print(f"Wrote {out_path}  (early t={early}, late t={late})")


if __name__ == "__main__":
    main()
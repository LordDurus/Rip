import argparse
import os
import sqlite3
import pandas as pd
import numpy as np
import shutil
import subprocess
from pathlib import Path
import plotly.graph_objects as go

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
    df = pd.read_sql_query(
        "SELECT timestep FROM timestep_summary WHERE run_id = ? ORDER BY total_matter DESC LIMIT 1",
        conn, params=(run_id,)
    )
    if df.empty:
        return None
    return int(df["timestep"].iloc[0])


def load_cells(conn, run_id, timestep):
    """Load cell positions, density, and black hole status."""
    return pd.read_sql_query(
        """
        SELECT cp.col, cp.row, c.layer,
               c.matter_density, c.is_black_hole, c.rip_strength
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ?
        """,
        conn, params=(int(run_id), int(timestep))
    )


def main():
    print(f"Running: {os.path.basename(__file__)}")
    parser = argparse.ArgumentParser(description="3D visualization of simulation structure.")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--timestep", type=int, default=None,
                        help="Timestep to visualize (default: matter density peak)")
    parser.add_argument("--density-percentile", type=float, default=80,
                        help="Node threshold — cells above this percentile are nodes (default: 80)")
    parser.add_argument("--filament-low-percentile", type=float, default=50,
                        help="Filament lower bound — cells between this and density-percentile are filaments (default: 50)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip HTML output, PNG only")
    parser.add_argument("--no-png", action="store_true",
                        help="Skip PNG output, HTML only")
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
            timestep = 0
        print(f"Using matter density peak at timestep {timestep}")

    print(f"Run {run_id}, timestep {timestep}")

    df = load_cells(conn, run_id, timestep)
    conn.close()

    if df.empty:
        print("No data found.")
        return

    # Split into black holes and normal cells
    bh = df[df["is_black_hole"] == 1].copy()
    normal = df[df["is_black_hole"] == 0].copy()

    # Classify normal cells into nodes (top density_percentile%) and filaments (mid-band)
    node_thresh = np.percentile(normal["matter_density"], args.density_percentile)
    filament_low = np.percentile(normal["matter_density"], args.filament_low_percentile)

    nodes = normal[normal["matter_density"] >= node_thresh]
    filaments = normal[(normal["matter_density"] >= filament_low) &
                       (normal["matter_density"] < node_thresh)]
    # Voids (below filament_low) are not rendered — the black background says it all

    print(f"Black holes:    {len(bh)}")
    print(f"Node cells:     {len(nodes)} (top {100 - args.density_percentile:.0f}%)")
    print(f"Filament cells: {len(filaments)} "
          f"({args.filament_low_percentile:.0f}–{args.density_percentile:.0f}th percentile)")
    print(f"Node threshold:          {node_thresh:.4f}")
    print(f"Filament low threshold:  {filament_low:.4f}")

    traces = []

    # Filaments — transparent light green, rendered first (behind nodes)
    if len(filaments) > 0:
        filament_sample = filaments.sample(min(len(filaments), 20000), random_state=42) if len(filaments) > 20000 else filaments
        traces.append(go.Scatter3d(
            x=filament_sample["col"],
            y=filament_sample["row"],
            z=filament_sample["layer"],
            mode="markers",
            marker={
                "size": 1.5,
                "color": "lightgreen",
                "opacity": 0.25,
            },
            name=f"Filaments ({len(filaments)} cells)",
            hovertemplate="col=%{x}, row=%{y}, layer=%{z}<extra>Filament</extra>",
        ))

    # Nodes — plasma colorscale by density, rendered on top of filaments
    if len(nodes) > 0:
        traces.append(go.Scatter3d(
            x=nodes["col"],
            y=nodes["row"],
            z=nodes["layer"],
            mode="markers",
            marker={
                "size": 2.5,
                "color": nodes["matter_density"],
                "colorscale": "Plasma",
                "colorbar": {"title": "Matter Density", "x": 1.0},
                "opacity": 0.7,
            },
            name=f"Nodes (top {100 - args.density_percentile:.0f}%)",
            hovertemplate="col=%{x}, row=%{y}, layer=%{z}<br>density=%{marker.color:.4f}<extra></extra>",
        ))

    # Black holes — fixed cyan, slightly larger
    if len(bh) > 0:
        bh_sample = bh.sample(min(len(bh), 5000), random_state=42) if len(bh) > 5000 else bh
        traces.append(go.Scatter3d(
            x=bh_sample["col"],
            y=bh_sample["row"],
            z=bh_sample["layer"],
            mode="markers",
            marker={
                "size": 3,
                "color": "cyan",
                "opacity": 0.4,
            },
            name=f"Black holes ({len(bh)} total)",
            hovertemplate="col=%{x}, row=%{y}, layer=%{z}<extra>Black hole</extra>",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"3D Structure — Run {run_id}, timestep {timestep}",
        scene={
          "xaxis_title": "Col",
          "yaxis_title": "Row",
          "zaxis_title": "Layer",
          "bgcolor": "black",
          "xaxis": {"gridcolor": "#333", "zerolinecolor": "#333", "backgroundcolor": "black"},
          "yaxis": {"gridcolor": "#333", "zerolinecolor": "#333", "backgroundcolor": "black"},
          "zaxis": {"gridcolor": "#333", "zerolinecolor": "#333", "backgroundcolor": "black"},
      },
        paper_bgcolor="black",
        font={"color": "white"},
        legend={"x": 0, "y": 1},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"structure_3d_run{run_id}_t{timestep}"

    if not args.no_html:
        html_path = OUTPUT_DIR / f"{stem}.html"
        fig.write_html(str(html_path))
        print(f"Saved interactive: {html_path}")

    if not args.no_png:
        png_path = OUTPUT_DIR / f"{stem}.png"
        fig.write_image(str(png_path), width=1400, height=900)
        save_png(png_path)
        print(f"Saved static: {png_path}")


if __name__ == "__main__":
    main()
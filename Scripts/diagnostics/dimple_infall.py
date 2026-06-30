"""
dimple_infall.py  (read-only)

Upstream of the Bullet-Cluster offset: does the dark-matter analog (rip_dimple)
actually fall in and pass through, or does it sit pinned at the clumps' starting
positions while only the gas migrates? If the dimple never infalls there is no
leading-collisionless / lagging-gas geometry to measure, no matter what drag does.

The suspected mechanism is the fossil/re-sourcing problem (physics-problems.md
section 5) sharpened by one fact: black holes are FIXED cells. They form early at
the dense clump cores and never move; if rip_dimple is sourced at/near them, the
dimple is continuously replenished at the ORIGINAL clump columns even as the gas
falls to center -- pinning the dimple centroid regardless of transport.

Three views answer it:
  A. Distance-to-center vs time, per clump, gas vs dimple. Gas should collapse
     toward 0 (reaches center); a pinned dimple stays flat near its start distance.
     The infall ratio (dimple distance moved / gas distance moved) is printed.
  B. Total rip_dimple (non-BH) and black-hole count vs time -- is the field still
     being sourced (rising total, growing BH count)?
  C. Column profiles at start / collision / late: gas, dimple, and BH-count per
     column. Shows spatially whether the dimple bump and the BHs stay parked at the
     origin columns while the gas bump migrates to center.

VALID REGIME: the midpoint col-split tracks the two clumps cleanly only through the
first pass; after the gas crosses, LOW/HIGH membership mis-assigns, so read panel A
and the start/collision profiles, not the post-crossing tail.

Usage: py dimple_infall.py [--run-id N] [--stride 25] [--window 6]
         [--times T1 T2 T3] [--max-timestep T] [--db PATH]
"""
import argparse
import sqlite3
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"
OUTPUT_DIR = REPO / "output"

ORANGE = "tab:orange"
BLUE = "tab:blue"
GREEN = "tab:green"
PURPLE = "tab:purple"
GRAY = "gray"


def resolve_run_id(conn, requested):
    if requested is not None:
        return requested
    row = conn.execute("SELECT MAX(run_id) FROM cell").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("No runs found in cell table.")
    return int(row[0])


def n_cols(conn):
    return int(conn.execute("SELECT MAX(col) + 1 FROM cell_position").fetchone()[0])


def candidate_timesteps(conn, run_id, max_timestep):
    rows = conn.execute(
        "SELECT DISTINCT timestep FROM cell WHERE run_id=? ORDER BY timestep",
        (run_id,)).fetchall()
    ts = [int(r[0]) for r in rows]
    if max_timestep is not None:
        ts = [t for t in ts if t <= max_timestep]
    if not ts:
        raise SystemExit(f"No cell data for run_id={run_id}")
    return ts


def col_profile(conn, run_id, timestep, ncol):
    """One indexed query -> (gas, dimple, bh_count) arrays over col.
    gas/dimple exclude BH cells; bh_count is the per-col tally of BH cells."""
    gas = np.zeros(ncol)
    dim = np.zeros(ncol)
    bh = np.zeros(ncol)
    for col, g, d, b in conn.execute(
        """SELECT cp.col,
                  SUM(CASE WHEN c.is_black_hole=0 THEN c.matter_density ELSE 0 END),
                  SUM(CASE WHEN c.is_black_hole=0 THEN MAX(c.rip_dimple, 0.0) ELSE 0 END),
                  SUM(c.is_black_hole)
           FROM cell c JOIN cell_position cp ON c.cell_position_id=cp.cell_position_id
           WHERE c.run_id=? AND c.timestep=?
           GROUP BY cp.col""", (run_id, timestep)):
        i = int(col)
        gas[i] = g or 0.0
        dim[i] = d or 0.0
        bh[i] = b or 0.0
    return gas, dim, bh


def half_centroid(weights, lo, hi, window):
    """Density-weighted centroid in [lo, hi), windowed around the peak (linear;
    the infall regime is pre-crossing so clumps stay interior to their half).
    Returns None if the half is empty."""
    seg = weights[lo:hi]
    if seg.sum() <= 0:
        return None
    peak = lo + int(np.argmax(seg))
    a = max(lo, peak - window)
    b = min(hi, peak + window + 1)
    w = weights[a:b]
    if w.sum() <= 0:
        return None
    idx = np.arange(a, b)
    return float((idx * w).sum() / w.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=None)
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--times", type=int, nargs=3, default=None, metavar=("T1", "T2", "T3"),
                    help="three timesteps for the profile snapshots "
                         "(default: start, auto-detected collision, end)")
    ap.add_argument("--max-timestep", type=int, default=None)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")
    conn = sqlite3.connect(db)
    run_id = resolve_run_id(conn, args.run_id)
    ncol = n_cols(conn)
    center = ncol / 2.0
    mid = ncol // 2
    ts_all = candidate_timesteps(conn, run_id, args.max_timestep)
    tmin, tmax = ts_all[0], ts_all[-1]
    sampled = ts_all[::args.stride]
    if sampled[-1] != tmax:
        sampled.append(tmax)
    print(f"run {run_id}: {len(sampled)} samples ({tmin}..{tmax}, stride {args.stride}), "
          f"{ncol}-col axis (center {center:.0f}, split {mid})")

    # --- time series for panels A and B ---
    T = []
    lo_gas_d, lo_dim_d, hi_gas_d, hi_dim_d = [], [], [], []   # distance-to-center
    lo_gas_c, hi_gas_c = [], []                               # gas centroids (for collision detect)
    total_dim, bh_total = [], []
    for k, t in enumerate(sampled):
        gas, dim, bh = col_profile(conn, run_id, t, ncol)
        if gas.sum() <= 0:
            continue
        lg = half_centroid(gas, 0, mid, args.window)
        hg = half_centroid(gas, mid, ncol, args.window)
        ld = half_centroid(dim, 0, mid, args.window)
        hd = half_centroid(dim, mid, ncol, args.window)
        if lg is None or hg is None:
            continue
        T.append(t)
        lo_gas_c.append(lg); hi_gas_c.append(hg)
        lo_gas_d.append(abs(lg - center))
        hi_gas_d.append(abs(hg - center))
        lo_dim_d.append(abs(ld - center) if ld is not None else np.nan)
        hi_dim_d.append(abs(hd - center) if hd is not None else np.nan)
        total_dim.append(float(dim.sum()))
        bh_total.append(float(bh.sum()))
        if (k + 1) % 20 == 0 or k + 1 == len(sampled):
            print(f"  ...{k + 1}/{len(sampled)}", flush=True)
    if not T:
        raise SystemExit(f"No usable cell data for run_id={run_id}")
    T = np.array(T)

    # collision timestep = sample where the two gas centroids are closest
    sep = np.abs(np.array(hi_gas_c) - np.array(lo_gas_c))
    t_coll = int(T[int(np.argmin(sep))])

    # --- infall ratio (start -> collision), printed ---
    def at(arr, t):
        return arr[int(np.argmin(np.abs(T - t)))]
    print("\nInfall (distance to center moved, start -> collision):")
    for name, gd, dd in (("LOW", lo_gas_d, lo_dim_d), ("HIGH", hi_gas_d, hi_dim_d)):
        gas_in = at(gd, tmin) - at(gd, t_coll)
        dim_in = at(dd, tmin) - at(dd, t_coll)
        ratio = (dim_in / gas_in) if gas_in > 1e-9 else float("nan")
        print(f"  {name}: gas moved {gas_in:6.2f} cells, dimple {dim_in:6.2f} cells "
              f"-> dimple/gas = {ratio:5.2f}  (~0 = dimple pinned, ~1 = co-moving)")

    # --- profile snapshot timesteps ---
    if args.times:
        snaps = args.times
    else:
        snaps = [tmin, t_coll, tmax]
    snap_labels = ["start", f"collision (t={t_coll})", "late"] if not args.times \
        else [f"t={s}" for s in snaps]
    profiles = []
    for snap in snaps:
        # snap to the nearest available timestep (bind snap as default to avoid late-binding in lambda)
        s_real = min(ts_all, key=lambda x, snap=snap: abs(x - snap))
        profiles.append((s_real, col_profile(conn, run_id, s_real, ncol)))
    conn.close()

    # --- figure ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(12, 11))
    gs = gridspec.GridSpec(3, 3, height_ratios=[1.1, 0.9, 1.0], hspace=0.32, wspace=0.28)
    fig.suptitle(f"Dimple infall diagnostic — Run {run_id}  "
                 f"(is the dark-matter analog falling in, or pinned?)", fontsize=13)

    # Panel A: distance-to-center vs time
    plot_a = fig.add_subplot(gs[0, :])
    plot_a.plot(T, lo_gas_d, "-", color=ORANGE, label="LOW gas")
    plot_a.plot(T, lo_dim_d, "--", color=ORANGE, label="LOW dimple")
    plot_a.plot(T, hi_gas_d, "-", color=BLUE, label="HIGH gas")
    plot_a.plot(T, hi_dim_d, "--", color=BLUE, label="HIGH dimple")
    plot_a.axvline(t_coll, color=GRAY, ls=":", lw=1.0, label=f"collision (t={t_coll})")
    plot_a.set_ylabel("distance to center (cells)")
    plot_a.set_title("A. Infall: gas should collapse toward 0; a pinned dimple stays flat",
                 fontsize=10, loc="left")
    plot_a.legend(loc="upper right", fontsize=8, ncol=3)
    plot_a.grid(True, alpha=0.3)

    # Panel B: total dimple + BH count vs time
    subplot_a = fig.add_subplot(gs[1, :])
    subplot_a.plot(T, total_dim, color=PURPLE, label="total rip_dimple (non-BH)")
    subplot_a.set_ylabel("total rip_dimple", color=PURPLE)
    subplot_a.tick_params(axis="y", labelcolor=PURPLE)
    subplot_a.set_title("B. Sourcing: rising total + growing BH count = dimple still being created",
                 fontsize=10, loc="left")
    subplot_a.grid(True, alpha=0.3)
    plot_b = subplot_a.twinx()
    plot_b.plot(T, bh_total, color=GRAY, lw=1.2, label="black-hole cells")
    plot_b.set_ylabel("black-hole cell count", color=GRAY)
    plot_b.tick_params(axis="y", labelcolor=GRAY)
    subplot_a.axvline(t_coll, color=GRAY, ls=":", lw=1.0)

    # Panel C: column profiles at start / collision / late
    for j, (s_real, (gas, dim, bh)) in enumerate(profiles):
        sublot_c = fig.add_subplot(gs[2, j])
        cols = np.arange(ncol)
        gmax = gas.max() if gas.max() > 0 else 1.0
        dmax = dim.max() if dim.max() > 0 else 1.0
        sublot_c.fill_between(cols, gas / gmax, color=ORANGE, alpha=0.45, label="gas (norm)")
        sublot_c.plot(cols, dim / dmax, color=PURPLE, lw=1.4, label="dimple (norm)")
        if bh.max() > 0:
            sublot_c.bar(cols, bh / bh.max() * 0.5, width=1.0, color=GRAY, alpha=0.5,
                   label="BH count (norm)")
        sublot_c.axvline(center, color=GRAY, ls=":", lw=0.8)
        sublot_c.set_xlabel("col")
        sublot_c.set_title(f"{snap_labels[j]}", fontsize=9)
        if j == 0:
            sublot_c.set_ylabel("normalized")
            sublot_c.legend(fontsize=7, loc="upper center")
        sublot_c.set_ylim(0, 1.05)
        sublot_c.grid(True, alpha=0.3)

    out = OUTPUT_DIR / f"dimple_infall_run{run_id}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
"""First-pass Bullet-Cluster offset diagnostic.

Reads the gas-vs-dimple offset at the FIRST closest approach of the two
colliding clumps, found automatically -- so you stop eyeballing which
timestep is clean. Method:

  1. Project non-BH gas (matter_density) onto the collision axis (col),
     summing over row and layer, at each scanned timestep. Aggregation is
     pushed into SQLite via the (run_id, timestep) index so this stays cheap
     even on a multi-hundred-GB rip_data.db.
  2. Split the col axis at the box midpoint into a left and a right clump,
     locate each clump's gas peak, and take a windowed density-weighted
     centroid around it. Clump separation = right centroid - left centroid.
  3. Coarse-scan separation to bracket the first local minimum (first
     closest approach), then refine at stride 1 inside the bracket.
  4. At that timestep, report the per-clump offset between the gas centroid
     (matter_density) and the dimple centroid (positive rip_dimple, the
     collisionless dark-matter proxy). Gas lagging behind the dimple is the
     Bullet-Cluster signature.

IMPORTANT: the fixed midpoint col-split only tracks the original two clumps
up to the first crossing. This script deliberately reads at / just before
first closest approach for exactly that reason; offsets sampled after the
clumps cross are meaningless with this split.

Examples:
    py bullet_offset_firstpass.py
    py bullet_offset_firstpass.py --run-id 7 --coarse-stride 20 --window 8
    py bullet_offset_firstpass.py --max-timestep 1800 --no-plot
"""

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"
OUTPUT_DIR = REPO / "output"

# ---------------------------------------------------------------------------
# run / grid resolution
# ---------------------------------------------------------------------------

def resolve_run_id(conn, requested):
    if requested is not None:
        row = conn.execute(
            "SELECT run_id, status FROM run WHERE run_id = ?", (requested,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"Run ID {requested} not found.")
        print(f"Using requested run_id={row[0]} (status: {row[1]})")
        return row[0]
    row = conn.execute(
        "SELECT run_id FROM run WHERE status = 'completed' "
        "ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise SystemExit("No completed runs found. Pass --run-id to force one.")
    print(f"Using most recent completed run_id={row[0]}")
    return row[0]


def n_cols(conn):
    row = conn.execute("SELECT MAX(col) FROM cell_position").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("cell_position is empty -- no grid to project onto.")
    return int(row[0]) + 1


def candidate_timesteps(conn, run_id, max_timestep):
    # timestep_summary has one cheap row per timestep; authoritative list.
    rows = conn.execute(
        "SELECT timestep FROM timestep_summary WHERE run_id = ? ORDER BY timestep",
        (run_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(f"No timestep_summary rows for run_id={run_id}.")
    ts = [int(r[0]) for r in rows]
    if max_timestep is not None:
        ts = [t for t in ts if t <= max_timestep]
    if not ts:
        raise SystemExit("No timesteps in the requested range.")
    return ts


# ---------------------------------------------------------------------------
# per-timestep col projection
# ---------------------------------------------------------------------------

def col_profiles(conn, run_id, timestep, ncol):
    """Return (gas, dimple) weight arrays over col for one timestep.

    gas    = sum of matter_density (non-BH) over row+layer per col
    dimple = sum of positive rip_dimple (non-BH) over row+layer per col
    """
    rows = conn.execute(
        """
        SELECT cp.col,
               SUM(c.matter_density),
               SUM(MAX(c.rip_dimple, 0.0))
        FROM cell c
        JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
        WHERE c.run_id = ? AND c.timestep = ? AND c.is_black_hole = 0
        GROUP BY cp.col
        """,
        (run_id, timestep),
    ).fetchall()
    gas = np.zeros(ncol)
    dimple = np.zeros(ncol)
    for col, g, d in rows:
        gas[int(col)] = g or 0.0
        dimple[int(col)] = d or 0.0
    return gas, dimple


def windowed_centroid(weights, lo, hi, window):
    """Density-weighted centroid in [lo, hi), windowed around the peak."""
    seg = weights[lo:hi]
    total = seg.sum()
    if total <= 0:
        return None
    peak = lo + int(np.argmax(seg))
    a = max(lo, peak - window)
    b = min(hi, peak + window + 1)
    w = weights[a:b]
    if w.sum() <= 0:
        return None
    idx = np.arange(a, b)
    return float((idx * w).sum() / w.sum())


def measure(conn, run_id, timestep, ncol, window):
    """Centroids + separation + per-clump gas-dimple offset at one timestep.

    Returns a dict or None if the clumps can't be located.
    """
    gas, dimple = col_profiles(conn, run_id, timestep, ncol)
    if gas.sum() <= 0:
        return None
    mid = ncol // 2

    left_gas = windowed_centroid(gas, 0, mid, window)
    right_gas = windowed_centroid(gas, mid, ncol, window)
    left_dim = windowed_centroid(dimple, 0, mid, window)
    right_dim = windowed_centroid(dimple, mid, ncol, window)

    if left_gas is None or right_gas is None:
        return None

    return {
        "timestep": timestep,
        "left_gas": left_gas,
        "right_gas": right_gas,
        "left_dim": left_dim,
        "right_dim": right_dim,
        # signed; positive while right clump sits to the right of left clump
        "separation": right_gas - left_gas,
        "left_offset": (left_gas - left_dim) if left_dim is not None else None,
        "right_offset": (right_gas - right_dim) if right_dim is not None else None,
    }


# ---------------------------------------------------------------------------
# first-closest-approach search
# ---------------------------------------------------------------------------

def coarse_scan(conn, run_id, ncol, window, timesteps, stride):
    sampled = timesteps[::stride]
    if sampled[-1] != timesteps[-1]:
        sampled.append(timesteps[-1])
    results = []
    warned_empty = False
    for t in sampled:
        m = measure(conn, run_id, t, ncol, window)
        if m is None:
            if not warned_empty:
                print(f"  (timestep {t} had no usable cells -- skipping; "
                      "cell-save stride may differ from summary)")
                warned_empty = True
            continue
        results.append(m)
    if not results:
        raise SystemExit("Could not locate clumps at any scanned timestep.")
    return results


def first_closest_approach_index(seps, approach_frac):
    """Index of the bottom of the FIRST real approach.

    The clumps start near their maximum separation and sit there (with
    sub-cell noise) until they actually collide. A plain local-minimum test
    fires on that pre-collision noise, so instead we wait for separation to
    drop below approach_frac * (initial separation) -- the onset of a genuine
    approach -- then walk down to the valley bottom of that first dip.

    Returns (index, used_fallback). used_fallback is True when no clear
    approach was seen and we fell back to the global minimum.
    """
    mags = [abs(s) for s in seps]
    baseline = mags[0]
    threshold = approach_frac * baseline
    # Cells of jitter to ride through. Under drag the gas redistributes and the
    # windowed separation picks up sub-cell wobble; a strict 'while decreasing'
    # walk stops at the first such uptick -- a pre-collision FALSE minimum (this
    # is why the drag sweep reported min_sep ~16 at t~420 when the real collision
    # is ~7 at t~600). The margin must exceed that wobble but stay well below a
    # genuine post-collision recovery (tens of cells).
    margin = max(2.0, 0.08 * baseline)

    onset = next((i for i, m in enumerate(mags) if m < threshold), None)
    if onset is None:
        # No clear first-pass collision in range; best we can do is global min.
        return int(np.argmin(mags)), True

    # Running-minimum walk from onset: track the deepest point of the first dip
    # and only stop once separation has RECOVERED more than `margin` above it, so
    # intra-dip jitter can't end the walk early. This finds the true bottom of the
    # first approach, not the first noise wiggle after onset.
    run_min = mags[onset]
    run_min_idx = onset
    j = onset
    while j + 1 < len(mags):
        j += 1
        if mags[j] < run_min:
            run_min = mags[j]
            run_min_idx = j
        elif mags[j] > run_min + margin:
            break
    return run_min_idx, False


def refine(conn, run_id, ncol, window, timesteps, lo_t, hi_t):
    band = [t for t in timesteps if lo_t <= t <= hi_t]
    best = None
    for t in band:
        m = measure(conn, run_id, t, ncol, window)
        if m is None:
            continue
        if best is None or abs(m["separation"]) < abs(best["separation"]):
            best = m
    return best


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def report(best, coarse, ncol, window, stride, baseline, used_fallback,
           show_trajectory=True):
    print()
    print("=" * 64)
    print("FIRST CLOSEST APPROACH")
    print("=" * 64)
    print(f"grid cols           : {ncol}  (split at col {ncol // 2})")
    print(f"centroid window      : +/-{window} cells around each clump peak")
    print(f"coarse stride        : {stride}")
    print(f"initial separation   : {baseline:.2f} cells")
    print("-" * 64)
    if used_fallback:
        print("!! No clear first-pass approach found (separation never dropped")
        print("   below the --approach-frac threshold). Reporting the GLOBAL")
        print("   minimum instead -- lower --approach-frac if the clumps did")
        print("   collide, or the run may not have produced a close pass.")
        print("-" * 64)
    t = best["timestep"]
    print(f"timestep             : {t}")
    print(f"left gas centroid    : col {fmt(best['left_gas'])}")
    print(f"right gas centroid   : col {fmt(best['right_gas'])}")
    sep = abs(best["separation"])
    print(f"clump separation     : {fmt(sep)} cells")
    print("-" * 64)
    print("GAS - DIMPLE OFFSET  (gas minus dark-matter proxy; lag = signature)")
    print(f"  left clump  offset : {fmt(best['left_offset'])} cells  "
          f"(gas {_lag_word(best['left_offset'])} dimple)")
    print(f"  right clump offset : {fmt(best['right_offset'])} cells  "
          f"(gas {_lag_word(best['right_offset'])} dimple)")
    print("=" * 64)

    if sep < 2 * window:
        print(f"!! separation ({sep:.1f}) < 2*window ({2 * window}): the two")
        print("   centroid windows overlap here, so each centroid is")
        print("   contaminated by the other clump and the offset is smeared.")
        print(f"   Re-run with --window {max(1, int(sep // 2))} or read the")
        print("   offset from the frames just BEFORE closest approach (plot/")
        print("   trajectory below), where the clumps are still resolved.")
    crossed = best["separation"] < 0
    if crossed:
        print("!! centroids have CROSSED at this timestep (right is left of left).")
        print("   The midpoint split no longer tracks the original clumps here;")
        print("   trust the last pre-crossing sample for the clean offset.")
    print("NOTE: midpoint col-split is only valid through the first pass.")
    if show_trajectory:
        print()
        print("Coarse separation trajectory (timestep : |separation|):")
        for m in coarse:
            mark = "  <-- closest" if m["timestep"] == t else ""
            print(f"  {m['timestep']:>6} : {abs(m['separation']):6.2f}{mark}")
    else:
        print(f"(coarse trajectory of {len(coarse)} samples suppressed; "
              "see offset_firstpass plot)")


def _lag_word(offset):
    if offset is None:
        return "vs"
    if offset > 0:
        return "leads (+col of)"
    if offset < 0:
        return "lags (-col of)"
    return "coincident with"


def make_plot(coarse, best, run_id):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping plot.")
        return

    ts = [m["timestep"] for m in coarse]
    sep = [abs(m["separation"]) for m in coarse]
    loff = [m["left_offset"] for m in coarse]
    roff = [m["right_offset"] for m in coarse]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.suptitle(f"First-pass collision diagnostic -- Run {run_id}", fontsize=13)

    ax1.plot(ts, sep, color="steelblue", marker="o", ms=3, lw=1.3)
    ax1.axvline(best["timestep"], color="tomato", ls="--",
                label=f"first closest approach (t={best['timestep']})")
    ax1.set_ylabel("|clump separation| (cells)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.plot(ts, loff, color="seagreen", marker="o", ms=3, lw=1.2,
             label="left clump gas-dimple offset")
    ax2.plot(ts, roff, color="darkorange", marker="o", ms=3, lw=1.2,
             label="right clump gas-dimple offset")
    ax2.axhline(0, color="gray", lw=0.8)
    ax2.axvline(best["timestep"], color="tomato", ls="--")
    ax2.set_xlabel("timestep")
    ax2.set_ylabel("gas - dimple (cells)")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"offset_firstpass_run{run_id}.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Saved plot: {out}")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Auto-detect the first closest approach and report the "
                    "gas-dimple offset there."
    )
    parser.add_argument("--run-id", type=int, default=None,
                        help="Run ID (default: most recent completed run).")
    parser.add_argument("--coarse-stride", type=int, default=25,
                        help="Timestep stride for the coarse separation scan "
                             "(default: 25).")
    parser.add_argument("--window", type=int, default=8,
                        help="Half-width (cells) of the centroid window around "
                             "each clump peak (default: 8).")
    parser.add_argument("--max-timestep", type=int, default=None,
                        help="Only scan timesteps <= this (default: all).")
    parser.add_argument("--approach-frac", type=float, default=0.6,
                        help="A real approach is registered only once separation "
                             "drops below this fraction of its initial value; "
                             "rejects pre-collision plateau noise (default: 0.6).")
    parser.add_argument("--no-plot", action="store_true",
                        help="Skip writing the diagnostic PNG.")
    parser.add_argument("--no-trajectory", action="store_true",
                        help="Suppress the per-sample coarse trajectory table "
                             "(keeps the summary + warnings). Use when redirecting "
                             "into validation.txt to avoid hundreds of lines.")
    parser.add_argument("--json", action="store_true",
                        help="Also print one machine-readable JSON line with the "
                             "closest-approach result (for the sweep harness).")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_id = resolve_run_id(conn, args.run_id)
        ncol = n_cols(conn)
        timesteps = candidate_timesteps(conn, run_id, args.max_timestep)
        print(f"Scanning {len(timesteps)} timesteps "
              f"(coarse stride {args.coarse_stride}) on a {ncol}-col axis...")

        coarse = coarse_scan(conn, run_id, ncol, args.window,
                             timesteps, args.coarse_stride)
        seps = [m["separation"] for m in coarse]
        baseline = abs(seps[0])
        i, used_fallback = first_closest_approach_index(seps, args.approach_frac)

        lo_t = coarse[max(0, i - 1)]["timestep"]
        hi_t = coarse[min(len(coarse) - 1, i + 1)]["timestep"]
        print(f"Coarse minimum bracketed in [{lo_t}, {hi_t}]; refining at stride 1...")

        best = refine(conn, run_id, ncol, args.window, timesteps, lo_t, hi_t)
        if best is None:
            best = coarse[i]
    finally:
        conn.close()

    report(best, coarse, ncol, args.window, args.coarse_stride,
           baseline, used_fallback, show_trajectory=not args.no_trajectory)

    if args.json:
        sep = abs(best["separation"])
        print("RESULT_JSON " + json.dumps({
            "run_id": run_id,
            "timestep": best["timestep"],
            "separation": round(sep, 3),
            "initial_separation": round(baseline, 3),
            "left_offset": (None if best["left_offset"] is None
                            else round(best["left_offset"], 3)),
            "right_offset": (None if best["right_offset"] is None
                             else round(best["right_offset"], 3)),
            "window": args.window,
            "overlap": sep < 2 * args.window,
            "used_fallback": used_fallback,
        }))

    if not args.no_plot:
        make_plot(coarse, best, run_id)


if __name__ == "__main__":
    main()
"""First-pass Bullet-Cluster offset diagnostic (single-window snapshot).

Reads the gas-vs-dimple offset at the FIRST closest approach of the two
colliding clumps within a --max-timestep window, so plot.bat can show the
collision developing across a staged series of windows. Method:

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

TWO-PHASE RUNS: when the collision is triggered by a delayed velocity kick
(BULLET_KICK_RIP_RATE > 0), the real collision is at the logged kick
timestep. Windows that end BEFORE the kick contain only the pre-kick
gravitational drift, whose separation minimum is NOT the collision -- reading
it produces a misleading "observable" (gas and dimple coincident, dark
fraction ~2%) that has nothing to do with the engineered collision. So for a
two-phase run this script:
  - reads the "BULLET KICK fired" log line,
  - SKIPS entirely (prints a one-line notice, no measurement) when the
    requested --max-timestep precedes the kick, and
  - anchors the scan at the kick timestep otherwise.
A t=0-kick or no-kick run has no kick line and behaves exactly as before.

IMPORTANT: the fixed midpoint col-split only tracks the original two clumps
up to the first crossing. This script deliberately reads at / just before
first closest approach for exactly that reason; offsets sampled after the
clumps cross are meaningless with this split.

Examples:
    py offset_diagnostic.py
    py offset_diagnostic.py --run-id 7 --coarse-stride 20 --window 8
    py offset_diagnostic.py --max-timestep 1800 --no-plot
"""

import argparse
import os
import re
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


def kick_timestep_from_log(conn, run_id):
    """Return the timestep of the two-phase BULLET KICK, or None.

    Reads the log line create_data emits when the delayed kick fires:
      't=4760: BULLET KICK fired -- windowed rip rate ...'
    Returns None for t=0-kick / no-kick runs (no such line). Introspects the
    log table so a schema rename surfaces as 'no kick line' rather than crash.
    """
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    log_table = None
    for t in tables:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        if {"run_id", "message"} <= cols:
            log_table = t
            break
    if log_table is None:
        return None
    row = conn.execute(
        f"SELECT message FROM {log_table} "
        f"WHERE run_id = ? AND message LIKE '%BULLET KICK fired%' "
        f"ORDER BY rowid LIMIT 1",
        (run_id,),
    ).fetchone()
    if not row:
        return None
    m = re.search(r"t=(\d+): BULLET KICK fired", row[0])
    return int(m.group(1)) if m else None


def n_cols(conn):
    row = conn.execute("SELECT MAX(col) FROM cell_position").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("cell_position is empty -- no grid to project onto.")
    return int(row[0]) + 1


def candidate_timesteps(conn, run_id, max_timestep, scan_from):
    # timestep_summary has one cheap row per timestep; authoritative list.
    rows = conn.execute(
        "SELECT timestep FROM timestep_summary WHERE run_id = ? ORDER BY timestep",
        (run_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(f"No timestep_summary rows for run_id={run_id}.")
    ts = [int(r[0]) for r in rows]
    if scan_from is not None:
        ts = [t for t in ts if t >= scan_from]
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


def first_local_min(seps):
    """Index of the first local minimum of |separation| in a sequence."""
    mags = [abs(s) for s in seps]
    for i in range(1, len(mags) - 1):
        if mags[i] <= mags[i - 1] and mags[i] < mags[i + 1]:
            return i
    # No interior local min: clumps still approaching (or scan too short).
    return int(np.argmin(mags))


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


def report(best, coarse, ncol, window, stride, anchor_t):
    print()
    print("=" * 64)
    print("FIRST CLOSEST APPROACH")
    print("=" * 64)
    print(f"grid cols           : {ncol}  (split at col {ncol // 2})")
    print(f"centroid window      : +/-{window} cells around each clump peak")
    print(f"coarse stride        : {stride}")
    if anchor_t is not None:
        print(f"scan anchored at     : t>={anchor_t}  (post-kick, from log)")
    print("-" * 64)
    t = best["timestep"]
    print(f"timestep             : {t}")
    print(f"left gas centroid    : col {fmt(best['left_gas'])}")
    print(f"right gas centroid   : col {fmt(best['right_gas'])}")
    print(f"clump separation     : {fmt(abs(best['separation']))} cells")
    print("-" * 64)
    print("GAS - DIMPLE OFFSET  (gas minus dark-matter proxy; lag = signature)")
    print(f"  left clump  offset : {fmt(best['left_offset'])} cells  "
          f"(gas {_lag_word(best['left_offset'])} dimple)")
    print(f"  right clump offset : {fmt(best['right_offset'])} cells  "
          f"(gas {_lag_word(best['right_offset'])} dimple)")
    print("=" * 64)

    crossed = best["separation"] < 0
    if crossed:
        print("!! centroids have CROSSED at this timestep (right is left of left).")
        print("   The midpoint split no longer tracks the original clumps here;")
        print("   trust the last pre-crossing sample for the clean offset.")
    print("NOTE: midpoint col-split is only valid through the first pass.")
    print()
    print("Coarse separation trajectory (timestep : |separation|):")
    for m in coarse:
        mark = "  <-- closest" if m["timestep"] == t else ""
        print(f"  {m['timestep']:>6} : {abs(m['separation']):6.2f}{mark}")


def _lag_word(offset):
    if offset is None:
        return "vs"
    if offset > 0:
        return "leads (+col of)"
    if offset < 0:
        return "lags (-col of)"
    return "coincident with"


def make_plot(coarse, best, run_id, scan_end, anchor_t):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping plot.")
        return

    ts = [m["timestep"] for m in coarse]
    sep = [abs(m["separation"]) for m in coarse]
    loff = [np.nan if m["left_offset"] is None else m["left_offset"] for m in coarse]
    roff = [np.nan if m["right_offset"] is None else m["right_offset"] for m in coarse]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.suptitle(f"First-pass collision diagnostic -- Run {run_id}", fontsize=13)

    ax1.plot(ts, sep, color="steelblue", marker="o", ms=3, lw=1.3)
    ax1.axvline(best["timestep"], color="tomato", ls="--",
                label=f"first closest approach (t={best['timestep']})")
    if anchor_t is not None:
        ax1.axvline(anchor_t, color="purple", ls=":", lw=1.2,
                    label=f"kick (t={anchor_t})")
    ax1.set_ylabel("|clump separation| (cells)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.plot(ts, loff, color="seagreen", marker="o", ms=3, lw=1.2,
             label="left clump gas-dimple offset")
    ax2.plot(ts, roff, color="darkorange", marker="o", ms=3, lw=1.2,
             label="right clump gas-dimple offset")
    ax2.axhline(0, color="gray", lw=0.8)
    ax2.axvline(best["timestep"], color="tomato", ls="--")
    if anchor_t is not None:
        ax2.axvline(anchor_t, color="purple", ls=":", lw=1.2)
    ax2.set_xlabel("timestep")
    ax2.set_ylabel("gas - dimple (cells)")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"offset_diagnostic_run{run_id}_t{scan_end}.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Saved plot: {out}")


# ---------------------------------------------------------------------------

def main():
    print(f"Running: {os.path.basename(__file__)}")
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
    parser.add_argument("--no-kick-anchor", action="store_true",
                        help="Ignore the BULLET KICK log line and scan the whole "
                             "window (pre-two-phase behavior).")
    parser.add_argument("--no-plot", action="store_true",
                        help="Skip writing the diagnostic PNG.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_id = resolve_run_id(conn, args.run_id)
        ncol = n_cols(conn)

        # Two-phase anchor. For a two-phase run, a window that ends before the
        # kick holds only pre-kick drift -- reading its separation minimum
        # yields a misleading "observable" unrelated to the engineered
        # collision (this is the t=225-vs-t=4760 bug). So: skip such windows
        # outright, and anchor the scan at the kick for windows that reach it.
        anchor_t = None
        if not args.no_kick_anchor:
            kt = kick_timestep_from_log(conn, run_id)
            if kt is not None:
                if args.max_timestep is not None and args.max_timestep < kt:
                    print(f"Two-phase run: kick fires at t={kt}, but this window "
                          f"ends at t={args.max_timestep} (pre-kick).")
                    print("SKIPPING -- a pre-kick window measures gravitational "
                          "drift, not the collision. No offset reported for this "
                          "window (this is expected, not a failure).")
                    return
                anchor_t = kt
                print(f"Two-phase run: anchoring scan at kick timestep t={kt} "
                      f"(from log).")

        timesteps = candidate_timesteps(conn, run_id, args.max_timestep, anchor_t)
        print(f"Scanning {len(timesteps)} timesteps "
              f"(coarse stride {args.coarse_stride}) on a {ncol}-col axis...")

        coarse = coarse_scan(conn, run_id, ncol, args.window,
                             timesteps, args.coarse_stride)
        seps = [m["separation"] for m in coarse]
        i = first_local_min(seps)

        lo_t = coarse[max(0, i - 1)]["timestep"]
        hi_t = coarse[min(len(coarse) - 1, i + 1)]["timestep"]
        print(f"Coarse minimum bracketed in [{lo_t}, {hi_t}]; refining at stride 1...")

        best = refine(conn, run_id, ncol, args.window, timesteps, lo_t, hi_t)
        if best is None:
            best = coarse[i]
    finally:
        conn.close()

    report(best, coarse, ncol, args.window, args.coarse_stride, anchor_t)

    if not args.no_plot:
        scan_end = args.max_timestep if args.max_timestep is not None else coarse[-1]["timestep"]
        make_plot(coarse, best, run_id, scan_end, anchor_t)


if __name__ == "__main__":
    main()
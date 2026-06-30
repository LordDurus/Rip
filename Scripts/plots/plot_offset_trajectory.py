"""
plot_offset_trajectory.py  (read-only)

The keystone Bullet Cluster diagnostic: the gas-dimple offset across the WHOLE run,
so you read the signal at the right moment (just after closest approach) instead of
guessing a --timestep. Three panels vs time:
  1. clump gas & dimple centroid positions along the collision axis
  2. clump separation (gas) -- dips at closest approach
  3. per-clump gas-dimple offset along travel -- POSITIVE = dimple leads gas =
     the Bullet Cluster signature
Blown-up timesteps (max non-BH matter_density over the ceiling) are shaded red.

PERFORMANCE: samples timesteps explicitly (WHERE timestep=?) so each query uses the
(run_id, timestep) index, and lets SQL do the depth-sum projection (GROUP BY col,row)
-> ~N^2 rows per timestep, not ~N^3 cells. A "timestep % stride" filter or pulling
raw cells into a Python loop would be orders of magnitude slower on a large DB.

Membership uses the midplane split by default (clean pre-crossing); pass --centers
A B to pin it. After the clumps cross, the midplane split mis-assigns them, so the
post-crossing offset is rough unless you re-aim --centers.

Centroids, separation, and offset are PERIODIC (circular) on the collision axis, so a
clump crossing the box seam produces no spurious jump. Pass --baseline RUN_ID to
overlay a null (drag=0) run's offset as faint dotted lines: gas and dimple differ in
their intrinsic dynamics even at drag=0, so the real drag signal is (run - null), not
the absolute offset -- the overlay makes that gap readable directly.

Usage: py plot_offset_trajectory.py [--run-id 1] [--baseline RUN_ID] [--stride 25]
         [--axis col|row] [--window 6] [--centers A B] [--matter-ceiling 1e4] [--db PATH]
"""
import argparse
import sqlite3
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
GRAY = "gray"


def _circ_mean(positions, weights, n):
    """Weighted circular mean of ring positions (size n) -> [0, n), or nan."""
    theta = 2.0 * np.pi * positions / n
    sw = float((weights * np.sin(theta)).sum())
    cw = float((weights * np.cos(theta)).sum())
    if np.isclose(sw, 0.0, rtol=1e-09, atol=1e-09) and np.isclose(cw, 0.0, rtol=1e-09, atol=1e-09):
        return float("nan")
    return float((np.arctan2(sw, cw) % (2.0 * np.pi)) * n / (2.0 * np.pi))


def _circ_dist(a, b, n):
    """Shortest distance on a ring of size n (handles arrays + nan)."""
    d = np.abs(np.asarray(a, float) - np.asarray(b, float)) % n
    return np.minimum(d, n - d)


def _circ_signed(target, ref, n):
    """Signed shortest offset target-ref on a ring of size n, in [-n/2, n/2)."""
    return ((target - ref + n / 2.0) % n) - n / 2.0


def peak_centroid(grid, mask, ax, window, n_ax):
    """Density-weighted centroid along `ax` within +/-window of the masked peak.
    PERIODIC on `ax`: the window wraps the box seam and the centroid is a circular
    mean, so a clump straddling col 0 / n-1 produces no linear jump. Off-axis the
    window is clamped (clumps do not cross the transverse boundary). Returns a
    position in [0, n_ax), or nan if the masked region is empty."""
    region = np.where(mask, grid, 0.0)
    if region.sum() <= 0:
        return float("nan")
    pr, pc = np.unravel_index(int(np.argmax(region)), region.shape)
    peak_ax = pc if ax == 1 else pr
    peak_off = pr if ax == 1 else pc
    n_off = region.shape[0] if ax == 1 else region.shape[1]
    ax_idx = (peak_ax + np.arange(-window, window + 1)) % n_ax        # wrapped
    olo, ohi = max(0, peak_off - window), min(n_off, peak_off + window + 1)
    if ax == 1:
        sub = region[olo:ohi][:, ax_idx]                             # cols wrapped
        wax = sub.sum(axis=0)
    else:
        sub = region[:, olo:ohi][ax_idx, :]                          # rows wrapped
        wax = sub.sum(axis=1)
    if wax.sum() <= 0:
        return float("nan")
    return _circ_mean(ax_idx.astype(float), wax, n_ax)


def compute_run(conn, run_id, lo_mask, hi_mask, ax, window, n_ax, stride, matter_ceiling, shape):
    """Sample one run -> dict of centroid/offset trajectory arrays. Extracted so a
    --baseline run is computed through the identical pipeline."""
    tr = conn.execute("SELECT MIN(timestep), MAX(timestep) FROM cell WHERE run_id=?",
                      (run_id,)).fetchone()
    if tr is None or tr[0] is None:
        raise SystemExit(f"No cell data for run_id={run_id}")
    tmin, tmax = int(tr[0]), int(tr[1])
    steps = list(range(tmin, tmax + 1, stride))
    if steps[-1] != tmax:
        steps.append(tmax)
    print(f"run {run_id}: sampling {len(steps)} timesteps ({tmin}..{tmax}, stride {stride})")

    T, lo_g, lo_d, hi_g, hi_d, lo_off, hi_off, blown = ([] for _ in range(8))
    for n, ts in enumerate(steps):
        # SQL does the depth-sum projection -> ~N^2 rows, not ~N^3 cells.
        gas = np.zeros(shape); dim = np.zeros(shape)
        any_rows = False
        for col, row, gsum, dsum in conn.execute(
            """SELECT cp.col, cp.row, SUM(c.matter_density), SUM(c.rip_dimple)
               FROM cell c JOIN cell_position cp ON c.cell_position_id=cp.cell_position_id
               WHERE c.run_id=? AND c.timestep=? AND c.is_black_hole=0
               GROUP BY cp.col, cp.row""", (run_id, ts)):
            gas[int(row), int(col)] = gsum or 0.0
            dim[int(row), int(col)] = dsum or 0.0
            any_rows = True
        if not any_rows:
            continue
        # per-cell max (non-BH) for the blowup flag -- indexed, cheap
        mx = conn.execute(
            """SELECT MAX(matter_density) FROM cell
               WHERE run_id=? AND timestep=? AND is_black_hole=0""",
            (run_id, ts)).fetchone()[0]
        lg = peak_centroid(gas, lo_mask, ax, window, n_ax)
        ld = peak_centroid(dim, lo_mask, ax, window, n_ax)
        hg = peak_centroid(gas, hi_mask, ax, window, n_ax)
        hd = peak_centroid(dim, hi_mask, ax, window, n_ax)
        T.append(ts)
        lo_g.append(lg); lo_d.append(ld); hi_g.append(hg); hi_d.append(hd)
        lo_off.append(_circ_signed(ld, lg, n_ax) * (+1.0))
        hi_off.append(_circ_signed(hd, hg, n_ax) * (-1.0))
        blown.append(mx is not None and mx > matter_ceiling)
        if (n + 1) % 20 == 0 or n + 1 == len(steps):
            print(f"  ...{n + 1}/{len(steps)} timesteps", flush=True)
    if not T:
        raise SystemExit(f"No cell data for run_id={run_id}")
    return {
        "T": np.array(T),
        "lo_g": lo_g,
        "lo_d": lo_d,
        "hi_g": hi_g,
        "hi_d": hi_d,
        "lo_off": lo_off,
        "hi_off": hi_off,
        "blown": np.array(blown),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=1)
    ap.add_argument("--baseline", type=int, default=None,
                    help="run_id of a null (drag=0) run to overlay on the offset panel")
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--axis", choices=["col", "row"], default="col")
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--centers", type=float, nargs=2, default=None, metavar=("A", "B"))
    ap.add_argument("--matter-ceiling", type=float, default=1e4)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")
    conn = sqlite3.connect(db)

    mc, mr = conn.execute("SELECT MAX(col)+1, MAX(row)+1 FROM cell_position").fetchone()
    n_col, n_row = int(mc), int(mr)
    shape = (n_row, n_col)
    ax = 1 if args.axis == "col" else 0
    n_ax = n_col if args.axis == "col" else n_row
    split = (sum(args.centers) / 2.0) if args.centers else n_ax / 2.0
    coord = np.indices(shape)[ax]
    lo_mask = coord < split
    hi_mask = ~lo_mask

    run = compute_run(conn, args.run_id, lo_mask, hi_mask, ax, args.window, n_ax,
                      args.stride, args.matter_ceiling, shape)
    base = None
    if args.baseline is not None:
        if args.baseline == args.run_id:
            print("note: --baseline equals --run-id; skipping overlay")
        else:
            base = compute_run(conn, args.baseline, lo_mask, hi_mask, ax, args.window,
                               n_ax, args.stride, args.matter_ceiling, shape)
    conn.close()

    T = run["T"]; blown = run["blown"]
    def shade(a):
        for i in range(len(T)):
            if blown[i]:
                a.axvspan(T[i] - args.stride / 2, T[i] + args.stride / 2,
                          color="red", alpha=0.12, lw=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    base_note = f"  vs null run {args.baseline}" if base is not None else ""
    fig.suptitle(f"Gas-dimple offset trajectory — Run {args.run_id}{base_note} "
                 f"(axis={args.axis}, red = blown-up/unreliable)", fontsize=12)
    a1.plot(T, run["lo_g"], "-", color=ORANGE, label="LOW gas")
    a1.plot(T, run["lo_d"], "--", color=ORANGE, label="LOW dimple")
    a1.plot(T, run["hi_g"], "-", color=BLUE, label="HIGH gas")
    a1.plot(T, run["hi_d"], "--", color=BLUE, label="HIGH dimple")
    a1.set_ylabel(f"centroid ({args.axis})"); a1.legend(loc="upper right", fontsize=8)
    shade(a1); a1.grid(True, alpha=0.3)
    sep = _circ_dist(run["hi_g"], run["lo_g"], n_ax)
    a2.plot(T, sep, color=GREEN); a2.set_ylabel("clump separation (gas)")
    shade(a2); a2.grid(True, alpha=0.3)
    a3.axhline(0, color=GRAY, lw=0.8)
    if base is not None:
        # faint dotted = the null (drag=0); the gap to the solid drag curve of the
        # same color IS the drag signal (LOW pairs with LOW, HIGH with HIGH).
        a3.plot(base["T"], base["lo_off"], color=ORANGE, lw=1.0, ls=":", alpha=0.45,
                label=f"LOW null (run {args.baseline})")
        a3.plot(base["T"], base["hi_off"], color=BLUE, lw=1.0, ls=":", alpha=0.45,
                label=f"HIGH null (run {args.baseline})")
    a3.plot(T, run["lo_off"], color=ORANGE, label="LOW offset (dimple-lead +)")
    a3.plot(T, run["hi_off"], color=BLUE, label="HIGH offset (dimple-lead +)")
    a3.set_ylabel("offset along travel"); a3.set_xlabel("timestep")
    a3.legend(loc="upper left", fontsize=8); shade(a3); a3.grid(True, alpha=0.3)
    plt.tight_layout()
    tag = f"run{args.run_id}" + (f"_vs{args.baseline}" if base is not None else "")
    out = OUTPUT_DIR / f"offset_trajectory_{tag}.png"
    plt.savefig(out, dpi=150); plt.close()
    nb = int((~blown).sum())
    print(f"{len(T)} frames ({nb} valid, {len(T)-nb} blown-up)")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
"""
dimple_infall.py  (read-only)

Upstream of the Bullet-Cluster offset: does the dark-matter analog (rip_dimple)
actually fall in as two coherent halos that pass through, or does it disperse into
a near-uniform sea while only the gas keeps a clump? If the dimple floods the box
there is no leading-collisionless / lagging-gas geometry to measure, no matter what
drag does -- and a raw centroid will LIE, because the centroid of a uniform sea
sits at box center and looks "co-moving" when in fact no halo survives.

So this reads the dimple two ways at once:
  * RAW centroid of the dimple column-profile (what earlier versions used). Floods
    to center, so it reports a false "dimple reached the center" signal.
  * EXCESS centroid: subtract a per-timestep background (a robust percentile of the
    column profile -- the uniform-sea floor) and keep only the positive excess, so a
    flat sea contributes ZERO and only clump-concentrated DM has a centroid. When the
    excess vanishes the centroid is None: honestly "no halo here," not a fake number.

Four views:
  A. Distance-to-center vs time, per clump. Gas (solid) should collapse toward 0.
     EXCESS dimple (bold dashed) is the real DM-halo track; RAW dimple (faint dotted)
     is shown alongside so the gap between them = how much the flood is faking infall.
  B. Sourcing: total rip_dimple + black-hole count vs time (is the field still being
     created?).
  C. FLOOD metric: clumped fraction = excess mass / total dimple mass, per timestep.
     Starts ~1 (all dimple in the two halos), decays toward 0 as rips source a global
     sea that drowns them. The dissolution time (fraction first < 0.5) is the moment
     the two-halo geometry stops existing -- the ceiling on any Bullet-Cluster window.
     Peak contrast (peak / background) is overlaid faintly.
  D. Column profiles at start / collision / late: gas, RAW dimple, EXCESS dimple, and
     BH count. Shows spatially whether the dimple is two halos or a flat sea.

VALID REGIME: the midpoint col-split tracks the two clumps cleanly only through the
first pass; after the gas crosses, LOW/HIGH membership mis-assigns, so read panel A,
the clumped-fraction curve, and the start/collision profiles -- not the crossing tail.

Usage: py dimple_infall.py [--run-id N] [--stride 25] [--window 6]
         [--bg-percentile 50] [--times T1 T2 T3] [--max-timestep T] [--db PATH]
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


def background_level(profile, pct):
    """Robust 'uniform-sea floor' of a column profile: the pct-th percentile.
    A flat sea makes most columns equal, so the percentile lands on the sea; the
    two clump columns sit above it and become the excess."""
    if profile.size == 0:
        return 0.0
    return float(np.percentile(profile, pct))


def excess_profile(profile, bg):
    """Column profile with the background floor removed (negatives clipped).
    A uniform sea -> all zeros; only clump-concentrated mass survives."""
    e = profile - bg
    e[e < 0.0] = 0.0
    return e


def half_centroid(weights, lo, hi, window):
    """Density-weighted centroid in [lo, hi), windowed around the peak (linear;
    the infall regime is pre-crossing so clumps stay interior to their half).
    Returns None if the half has no positive weight -- which, on an EXCESS
    profile, is the honest 'no halo here' signal rather than a fake center."""
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


def dissolution_time(T, frac, thresh=0.5):
    """Timestep after which the clumped fraction never again reaches `thresh`: the
    point where the two DM halos are gone FOR GOOD. Defined as the sample right after
    the LAST one at/above thresh, so a brief early transient dip (which recovers, and
    so is not the last high) doesn't count -- only the final sustained collapse does.
    None if the fraction never reaches thresh (a sea from the start) or is still at/
    above it at the end of the run (halos survive)."""
    frac = np.asarray(frac, float)
    above = np.nonzero(frac >= thresh)[0]
    if above.size == 0:
        return None                        # never clumped
    last = int(above[-1])
    if last >= len(frac) - 1:
        return None                        # still clumped at the end -> survives
    return int(T[last + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=None)
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--bg-percentile", type=float, default=50.0,
                    help="percentile of the column profile taken as the uniform-sea "
                         "floor for the excess subtraction (default: 50 = median)")
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
    pct = args.bg_percentile
    ts_all = candidate_timesteps(conn, run_id, args.max_timestep)
    tmin, tmax = ts_all[0], ts_all[-1]
    sampled = ts_all[::args.stride]
    if sampled[-1] != tmax:
        sampled.append(tmax)
    print(f"run {run_id}: {len(sampled)} samples ({tmin}..{tmax}, stride {args.stride}), "
          f"{ncol}-col axis (center {center:.0f}, split {mid}), bg=p{pct:g}")

    # --- time series for panels A, B, C ---
    T = []
    lo_gas_d, hi_gas_d = [], []                 # gas distance-to-center
    lo_ex_d, hi_ex_d = [], []                   # EXCESS-dimple distance-to-center
    lo_ex_c, hi_ex_c = [], []                   # EXCESS-dimple signed centroid (for offset)
    lo_raw_d, hi_raw_d = [], []                 # RAW-dimple distance-to-center
    lo_gas_c, hi_gas_c = [], []                 # gas centroids (collision detect)
    total_dim, bh_total = [], []
    clumped_frac, contrast = [], []             # flood metrics
    for k, t in enumerate(sampled):
        gas, dim, bh = col_profile(conn, run_id, t, ncol)
        if gas.sum() <= 0:
            continue
        bg = background_level(dim, pct)
        exc = excess_profile(dim, bg)

        lg = half_centroid(gas, 0, mid, args.window)
        hg = half_centroid(gas, mid, ncol, args.window)
        if lg is None or hg is None:
            continue
        ld_raw = half_centroid(dim, 0, mid, args.window)
        hd_raw = half_centroid(dim, mid, ncol, args.window)
        ld_ex = half_centroid(exc, 0, mid, args.window)
        hd_ex = half_centroid(exc, mid, ncol, args.window)

        T.append(t)
        lo_gas_c.append(lg); hi_gas_c.append(hg)
        lo_gas_d.append(abs(lg - center))
        hi_gas_d.append(abs(hg - center))
        lo_ex_d.append(abs(ld_ex - center) if ld_ex is not None else np.nan)
        hi_ex_d.append(abs(hd_ex - center) if hd_ex is not None else np.nan)
        lo_ex_c.append(ld_ex if ld_ex is not None else np.nan)
        hi_ex_c.append(hd_ex if hd_ex is not None else np.nan)
        lo_raw_d.append(abs(ld_raw - center) if ld_raw is not None else np.nan)
        hi_raw_d.append(abs(hd_raw - center) if hd_raw is not None else np.nan)

        dtot = float(dim.sum())
        total_dim.append(dtot)
        bh_total.append(float(bh.sum()))
        clumped_frac.append(float(exc.sum() / dtot) if dtot > 0 else np.nan)
        contrast.append(float(dim.max() / bg) if bg > 0 else np.nan)
        if (k + 1) % 20 == 0 or k + 1 == len(sampled):
            print(f"  ...{k + 1}/{len(sampled)}", flush=True)
    if not T:
        raise SystemExit(f"No usable cell data for run_id={run_id}")
    T = np.array(T)
    clumped_frac = np.array(clumped_frac)

    # dissolution first: a Bullet-Cluster signal is only measurable while two DM
    # halos still exist, so it bounds the window we search for the gas collision.
    t_diss = dissolution_time(T, clumped_frac, 0.5)

    # gas closest approach WITHIN the halo-alive window. Global argmin lands in the
    # post-crossing separation noise (the midpoint split mis-assigns clumps after the
    # first pass), so restrict to t <= dissolution and take the deepest real approach.
    sep = np.abs(np.array(hi_gas_c) - np.array(lo_gas_c))
    in_win = (T <= t_diss) if t_diss is not None else np.ones(len(T), bool)
    sep_win = np.where(in_win, sep, np.inf)
    i_coll = int(np.argmin(sep_win))
    t_coll = int(T[i_coll])
    min_sep_win = float(sep[i_coll])

    # --- infall ratios (start -> collision), RAW vs EXCESS, printed ---
    def at(arr, t):
        return np.asarray(arr, float)[int(np.argmin(np.abs(T - t)))]

    print("\nInfall (distance-to-center moved, start -> collision):")
    print("  RAW dimple centroid (floods to center -> can fake co-moving):")
    for name, gd, dd in (("LOW", lo_gas_d, lo_raw_d), ("HIGH", hi_gas_d, hi_raw_d)):
        gas_in = at(gd, tmin) - at(gd, t_coll)
        dim_in = at(dd, tmin) - at(dd, t_coll)
        ratio = (dim_in / gas_in) if gas_in > 1e-9 else float("nan")
        print(f"    {name}: gas {gas_in:6.2f}, dimple {dim_in:6.2f} -> dimple/gas = {ratio:5.2f}")
    print("  EXCESS dimple centroid (sea removed -> real halo, or nan if dissolved):")
    for name, gd, dd in (("LOW", lo_gas_d, lo_ex_d), ("HIGH", hi_gas_d, hi_ex_d)):
        gas_in = at(gd, tmin) - at(gd, t_coll)
        dim_in = at(dd, tmin) - at(dd, t_coll)
        ratio = (dim_in / gas_in) if gas_in > 1e-9 else float("nan")
        tag = "  (excess GONE at collision)" if not np.isfinite(dim_in) else ""
        print(f"    {name}: gas {gas_in:6.2f}, dimple {dim_in:6.2f} -> dimple/gas = {ratio:5.2f}{tag}")

    def frac_at(t):
        return float(clumped_frac[int(np.argmin(np.abs(T - t)))])
    print("\nFlood metric -- clumped dimple fraction (excess mass / total mass):")
    print(f"  start (t={tmin}): {frac_at(tmin):.2f}   collision (t={t_coll}): {frac_at(t_coll):.2f}"
          f"   late (t={tmax}): {frac_at(tmax):.2f}")
    if t_diss is not None:
        print(f"  DM halos DISSOLVE (fraction < 0.5) at t~{t_diss} "
              f"-- two-halo geometry only exists before this.")
    elif np.all(clumped_frac < 0.5):
        print("  clumped fraction never reaches 0.5 -- two coherent halos never dominate "
              "(dimple is a sea from early on).")
    else:
        print("  clumped fraction stays >= 0.5 -- halos survive (no dissolution detected).")

    # --- excess-DM vs gas offset at the in-window closest approach (the signature) ---
    ex_lo_c = np.asarray(lo_ex_c, float)
    ex_hi_c = np.asarray(hi_ex_c, float)
    gas_lo_c = np.asarray(lo_gas_c, float)
    gas_hi_c = np.asarray(hi_gas_c, float)
    print(f"\nExcess-DM vs gas at closest approach within the halo-alive window (t={t_coll}):")
    if min_sep_win >= 2 * args.window:
        print(f"  gas-gas separation there is {min_sep_win:.2f} cells (>= 2*window="
              f"{2 * args.window}) -- the gas never got close while the halos were alive.")
        if t_diss is not None:
            print(f"  the halos dissolved (t~{t_diss}) BEFORE the gas collided: a timing "
                  "failure -- DM disperses faster than the clumps converge.")
    else:
        # travel direction: LOW moves +col toward center, HIGH moves -col toward center,
        # so 'DM leads gas' is +(excess - gas) for LOW and +(gas - excess) for HIGH.
        lead_lo = ex_lo_c[i_coll] - gas_lo_c[i_coll]
        lead_hi = gas_hi_c[i_coll] - ex_hi_c[i_coll]
        print(f"  gas-gas separation there: {min_sep_win:.2f} cells  (+ = DM ahead = signature)")
        for name, lead in (("LOW", lead_lo), ("HIGH", lead_hi)):
            if not np.isfinite(lead):
                print(f"  {name}: excess DM absent here -- no halo centroid to compare.")
            else:
                verdict = ("DM LEADS gas (Bullet signature)" if lead > 0.25
                           else "DM trails gas (wrong sign)" if lead < -0.25
                           else "coincident")
                print(f"  {name}: DM leads gas by {lead:+.2f} cells  -- {verdict}")

    # --- profile snapshot timesteps ---
    snaps = args.times if args.times else [tmin, t_coll, tmax]
    snap_labels = [f"t={s}" for s in snaps] if args.times \
        else ["start", f"collision (t={t_coll})", "late"]
    profiles = []
    for snap in snaps:
        s_real = min(ts_all, key=lambda x, snap=snap: abs(x - snap))
        profiles.append((s_real, col_profile(conn, run_id, s_real, ncol)))
    conn.close()

    # --- figure ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(12, 14))
    gs = gridspec.GridSpec(4, 3, height_ratios=[1.1, 0.8, 0.85, 1.0],
                           hspace=0.38, wspace=0.28)
    fig.suptitle(f"Dimple infall diagnostic — Run {run_id}  "
                 f"(coherent DM halo, or dispersed into a sea?)", fontsize=13)

    # Panel A: distance-to-center vs time -- gas, excess dimple, raw dimple
    plot_a = fig.add_subplot(gs[0, :])
    plot_a.plot(T, lo_gas_d, "-", color=ORANGE, label="LOW gas")
    plot_a.plot(T, hi_gas_d, "-", color=BLUE, label="HIGH gas")
    plot_a.plot(T, lo_ex_d, "--", color=ORANGE, lw=1.8, label="LOW dimple (excess)")
    plot_a.plot(T, hi_ex_d, "--", color=BLUE, lw=1.8, label="HIGH dimple (excess)")
    plot_a.plot(T, lo_raw_d, ":", color=ORANGE, lw=1.0, alpha=0.55, label="LOW dimple (raw)")
    plot_a.plot(T, hi_raw_d, ":", color=BLUE, lw=1.0, alpha=0.55, label="HIGH dimple (raw)")
    plot_a.axvline(t_coll, color=GRAY, ls=":", lw=1.0, label=f"collision (t={t_coll})")
    if t_diss is not None:
        plot_a.axvline(t_diss, color="tab:red", ls="--", lw=1.0, label=f"halos dissolve (t~{t_diss})")
    plot_a.set_ylabel("distance to center (cells)")
    plot_a.set_title("A. Infall: gas (solid) collapses; EXCESS dimple (bold dash) is the real "
                     "halo, RAW (dotted) floods to center", fontsize=10, loc="left")
    plot_a.legend(loc="upper right", fontsize=7, ncol=4)
    plot_a.grid(True, alpha=0.3)

    # Panel B: total dimple + BH count vs time
    subplot_b = fig.add_subplot(gs[1, :])
    subplot_b.plot(T, total_dim, color=PURPLE, label="total rip_dimple (non-BH)")
    subplot_b.set_ylabel("total rip_dimple", color=PURPLE)
    subplot_b.tick_params(axis="y", labelcolor=PURPLE)
    subplot_b.set_title("B. Sourcing: total dimple + BH count -- is the field still being created?",
                        fontsize=10, loc="left")
    subplot_b.grid(True, alpha=0.3)
    twin_b = subplot_b.twinx()
    twin_b.plot(T, bh_total, color=GRAY, lw=1.2, label="black-hole cells")
    twin_b.set_ylabel("black-hole cell count", color=GRAY)
    twin_b.tick_params(axis="y", labelcolor=GRAY)
    subplot_b.axvline(t_coll, color=GRAY, ls=":", lw=1.0)

    # Panel C: FLOOD metric -- clumped fraction (+ contrast on twin)
    plot_c = fig.add_subplot(gs[2, :])
    plot_c.plot(T, clumped_frac, color="tab:red", lw=1.6, label="clumped fraction (excess / total)")
    plot_c.axhline(0.5, color=GRAY, ls="--", lw=0.8)
    plot_c.axvline(t_coll, color=GRAY, ls=":", lw=1.0, label=f"collision (t={t_coll})")
    if t_diss is not None:
        plot_c.axvline(t_diss, color="tab:red", ls="--", lw=1.0, label=f"dissolve (t~{t_diss})")
    plot_c.set_ylabel("clumped fraction", color="tab:red")
    plot_c.tick_params(axis="y", labelcolor="tab:red")
    plot_c.set_ylim(0, 1.02)
    plot_c.set_title("C. Flood metric: fraction of dimple mass in the two halos vs a global sea "
                     "(1 = all halo, 0 = pure sea)", fontsize=10, loc="left")
    plot_c.legend(loc="upper right", fontsize=8)
    plot_c.grid(True, alpha=0.3)
    twin_c = plot_c.twinx()
    twin_c.plot(T, contrast, color=GRAY, lw=1.0, alpha=0.6, label="peak / background")
    twin_c.set_ylabel("peak contrast", color=GRAY)
    twin_c.tick_params(axis="y", labelcolor=GRAY)

    # Panel D: column profiles at start / collision / late
    for j, (s_real, (gas, dim, bh)) in enumerate(profiles):
        plot_d = fig.add_subplot(gs[3, j])
        cols = np.arange(ncol)
        bg = background_level(dim, pct)
        exc = excess_profile(dim, bg)
        gmax = gas.max() if gas.max() > 0 else 1.0
        dmax = dim.max() if dim.max() > 0 else 1.0
        plot_d.fill_between(cols, gas / gmax, color=ORANGE, alpha=0.40, label="gas (norm)")
        plot_d.plot(cols, dim / dmax, color=PURPLE, lw=1.2, alpha=0.55, label="dimple raw (norm)")
        plot_d.plot(cols, exc / dmax, color="tab:red", lw=1.6, label="dimple excess (norm)")
        if bh.max() > 0:
            plot_d.bar(cols, bh / bh.max() * 0.5, width=1.0, color=GRAY, alpha=0.4,
                       label="BH count (norm)")
        plot_d.axvline(center, color=GRAY, ls=":", lw=0.8)
        plot_d.set_xlabel("col")
        plot_d.set_title(f"{snap_labels[j]}", fontsize=9)
        if j == 0:
            plot_d.set_ylabel("normalized")
            plot_d.legend(fontsize=6.5, loc="upper center")
        plot_d.set_ylim(0, 1.05)
        plot_d.grid(True, alpha=0.3)

    out = OUTPUT_DIR / f"dimple_infall_run{run_id}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
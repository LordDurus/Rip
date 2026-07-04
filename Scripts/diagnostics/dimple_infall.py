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
  Also measures THE OBSERVABLE: the lensing proxy (gas + dimple = total non-BH
gravitating mass, what a lensing map would see) vs the gas alone -- both the
per-side centroid offset and the dark fraction of the mass. The Bullet-Cluster
observation needs BOTH: mass peaks offset from the gas AND the dark component
carrying most of the mass (observed clusters: dark ~5-6x the gas).

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
TAB_RED = "tab:red"


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


def n_rows(conn):
    row = conn.execute("SELECT MAX(row) FROM cell_position").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("cell_position is empty -- no grid.")
    return int(row[0]) + 1


def grid2d(conn, run_id, timestep, ncol, nrow):
    """One indexed query -> (gas2, dim2) arrays over (row, col), depth-summed,
    non-BH only. The 2D view that the 1D column projection washes out."""
    gas = np.zeros((nrow, ncol))
    dim = np.zeros((nrow, ncol))
    for col, row, g, d in conn.execute(
        """SELECT cp.col, cp.row,
                  SUM(CASE WHEN c.is_black_hole=0 THEN c.matter_density ELSE 0 END),
                  SUM(CASE WHEN c.is_black_hole=0 THEN MAX(c.rip_dimple, 0.0) ELSE 0 END)
           FROM cell c JOIN cell_position cp ON c.cell_position_id=cp.cell_position_id
           WHERE c.run_id=? AND c.timestep=?
           GROUP BY cp.col, cp.row""", (run_id, timestep)):
        gas[int(row), int(col)] = g or 0.0
        dim[int(row), int(col)] = d or 0.0
    return gas, dim


def smooth3(a):
    """3x3 box smoothing (edge-padded, numpy-only) so 2D peak-finding is not
    hijacked by single hot cells or the gas checkerboard mode."""
    p = np.pad(a, 1, mode="edge")
    h, w = a.shape
    return sum(p[i:i + h, j:j + w] for i in range(3) for j in range(3)) / 9.0


def disk_mask(shape, r0, c0, radius):
    rr, cc = np.ogrid[:shape[0], :shape[1]]
    return (rr - r0) ** 2 + (cc - c0) ** 2 <= radius ** 2


def halo2d_metrics(gas2, dim2, mid, pct, radius):
    """Per-timestep 2D halo measurements. For each half of the collision axis:
    the (smoothed) dimple peak and a disk of `radius` cells around it. Returns:
      halo_frac  -- excess dimple mass inside the two disks / total excess mass
                    (concentration: does a two-halo geometry exist?)
      halo_share -- disk excess / TOTAL dimple mass (comparable to the 1D
                    clumped fraction; how much of the whole field is halo)
      contrast   -- smoothed peak / percentile floor
      per side: dimple peak (row,col), in-halo dark fraction dimple/(gas+dimple),
                lensing-peak and gas-peak locations and their distance in cells."""
    floor = float(np.percentile(dim2, pct))
    exc2 = np.clip(dim2 - floor, 0.0, None)
    sm_dim = smooth3(dim2)
    sm_gas = smooth3(gas2)
    sm_lens = smooth3(gas2 + dim2)
    total_exc = float(exc2.sum())
    total_dim2 = float(dim2.sum())
    out = {"floor": floor}
    disk_exc = 0.0
    for side, c_lo, c_hi in (("LOW", 0, mid), ("HIGH", mid, dim2.shape[1])):
        seg = sm_dim[:, c_lo:c_hi]
        r0, c0 = np.unravel_index(int(np.argmax(seg)), seg.shape)
        c0 += c_lo
        m = disk_mask(dim2.shape, r0, c0, radius)
        disk_exc += float(exc2[m].sum())
        d_in = float(dim2[m].sum())
        g_in = float(gas2[m].sum())
        rl, cl = np.unravel_index(int(np.argmax(sm_lens[:, c_lo:c_hi])), seg.shape)
        rg, cg = np.unravel_index(int(np.argmax(sm_gas[:, c_lo:c_hi])), seg.shape)
        out[side] = {
            "peak": (int(r0), int(c0)),
            "dark_in": d_in / (d_in + g_in) if (d_in + g_in) > 0 else float("nan"),
            "lens_peak": (int(rl), int(cl + c_lo)),
            "gas_peak": (int(rg), int(cg + c_lo)),
            "lens_gas_off": float(np.hypot(rl - rg, cl - cg)),
        }
    out["halo_frac"] = disk_exc / total_exc if total_exc > 0 else float("nan")
    out["halo_share"] = disk_exc / total_dim2 if total_dim2 > 0 else float("nan")
    out["contrast"] = float(sm_dim.max() / floor) if floor > 0 else float("nan")
    return out


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


def dissolution_time(time, frac, thresh=0.5):
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
    return int(time[last + 1])


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
    ap.add_argument("--halo-radius", type=int, default=10,
                    help="Disk radius (cells) around each 2D dimple peak (default 10).")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")
    conn = sqlite3.connect(db)
    run_id = resolve_run_id(conn, args.run_id)
    ncol = n_cols(conn)
    nrow = n_rows(conn)
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
    lo_lens_c, hi_lens_c = [], []               # LENSING (gas+dimple) centroids
    dark_frac = []                              # dimple / (gas+dimple) mass fraction
    lo_gas_c, hi_gas_c = [], []                 # gas centroids (collision detect)
    total_dim, bh_total = [], []
    clumped_frac, contrast = [], []             # flood metrics
    halo_frac2, halo_share2 = [], []            # 2D concentration + mass share
    dark_in_lo, dark_in_hi = [], []             # 2D in-halo dark fraction per side
    lens_off_lo, lens_off_hi = [], []           # 2D lensing-vs-gas peak distance
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
        lens = gas + dim                        # what a lensing map sees (non-BH)
        ll = half_centroid(lens, 0, mid, args.window)
        hl = half_centroid(lens, mid, ncol, args.window)

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
        lo_lens_c.append(ll if ll is not None else np.nan)
        hi_lens_c.append(hl if hl is not None else np.nan)

        dtot = float(dim.sum())
        total_dim.append(dtot)
        bh_total.append(float(bh.sum()))
        clumped_frac.append(float(exc.sum() / dtot) if dtot > 0 else np.nan)
        gtot = float(gas.sum())
        dark_frac.append(dtot / (gtot + dtot) if (gtot + dtot) > 0 else np.nan)
        contrast.append(float(dim.max() / bg) if bg > 0 else np.nan)

        gas2, dim2 = grid2d(conn, run_id, t, ncol, nrow)
        h2 = halo2d_metrics(gas2, dim2, mid, pct, args.halo_radius)
        halo_frac2.append(h2["halo_frac"])
        halo_share2.append(h2["halo_share"])
        dark_in_lo.append(h2["LOW"]["dark_in"])
        dark_in_hi.append(h2["HIGH"]["dark_in"])
        lens_off_lo.append(h2["LOW"]["lens_gas_off"])
        lens_off_hi.append(h2["HIGH"]["lens_gas_off"])
        if (k + 1) % 20 == 0 or k + 1 == len(sampled):
            print(f"  ...{k + 1}/{len(sampled)}", flush=True)
    if not T:
        raise SystemExit(f"No usable cell data for run_id={run_id}")
    T = np.array(T)
    clumped_frac = np.array(clumped_frac)

    # dissolution first: a Bullet-Cluster signal is only measurable while two DM
    # halos still exist, so it bounds the window we search for the gas collision.
    t_diss = dissolution_time(T, clumped_frac, 0.5)
    halo_frac2 = np.asarray(halo_frac2, float)
    halo_share2 = np.asarray(halo_share2, float)
    t_diss2 = dissolution_time(T, halo_frac2, 0.5)

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

    # --- 2D halo metrics: the (col,row) view the 1D projection washes out ---
    def v_at(arr, t):
        return float(np.asarray(arr, float)[int(np.argmin(np.abs(T - t)))])

    print(f"\n2D HALO METRICS ((col,row) projection, disks r={args.halo_radius} around "
          f"each side's dimple peak):")
    print(f"  halo concentration 2D (disk excess / total excess): "
          f"start {v_at(halo_frac2, tmin):.2f}   collision {v_at(halo_frac2, t_coll):.2f}"
          f"   late {v_at(halo_frac2, tmax):.2f}")
    print(f"  halo mass share 2D (disk excess / total dimple):    "
          f"start {v_at(halo_share2, tmin):.2f}   collision {v_at(halo_share2, t_coll):.2f}"
          f"   late {v_at(halo_share2, tmax):.2f}")
    if t_diss2 is not None:
        print(f"  2D verdict: two-halo geometry DISSOLVES at t~{t_diss2}", end="")
    elif np.all(halo_frac2[np.isfinite(halo_frac2)] < 0.5):
        print("  2D verdict: never concentrated -- sea from the start", end="")
    else:
        print(f"  2D verdict: two-halo geometry SURVIVES to t={tmax}", end="")
    one_d_never = t_diss is None and bool(np.all(clumped_frac < 0.5))
    two_d_alive = t_diss2 is None and not bool(np.all(halo_frac2[np.isfinite(halo_frac2)] < 0.5))
    if two_d_alive and (t_diss is not None or one_d_never):
        what = f"dissolve at t~{t_diss}" if t_diss is not None else "no halos at all"
        print(f"   (1D said {what}: PROJECTION WASHOUT -- trust 2D)")
    elif t_diss is not None and t_diss2 is not None and t_diss2 > t_diss:
        print(f"   (1D said t~{t_diss}: projection undersold the halos)")
    else:
        print()
    print("  in-halo dark fraction (dimple/(gas+dimple) inside each disk; observed clusters ~0.83):")
    print(f"    LOW:  collision {v_at(dark_in_lo, t_coll):.2f} -> late {v_at(dark_in_lo, tmax):.2f}"
          f"      HIGH: collision {v_at(dark_in_hi, t_coll):.2f} -> late {v_at(dark_in_hi, tmax):.2f}")
    print(f"  lensing peak vs gas peak, 2D per-side distance (cells): "
          f"LOW {v_at(lens_off_lo, tmax):.1f}, HIGH {v_at(lens_off_hi, tmax):.1f} at late")

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

    # --- THE OBSERVABLE: would a lensing map peak off the gas? ---
    # Model-independent Bullet-Cluster signature: (a) the TOTAL gravitating mass
    # (gas + dimple; what lensing measures) sits offset from the gas, and (b) the
    # dark component carries most of that mass (observed: dark ~5-6x gas, i.e.
    # dark fraction ~0.83-0.86). Geometry alone cannot move the lensing peak off
    # the gas while the gas dominates the mass budget.
    dark_frac = np.asarray(dark_frac, float)
    lens_lo_c = np.asarray(lo_lens_c, float)
    lens_hi_c = np.asarray(hi_lens_c, float)
    df_coll = float(dark_frac[i_coll])
    print(f"\nTHE OBSERVABLE -- lensing map (gas+dimple) vs gas, at collision (t={t_coll}):")
    print(f"  dark fraction of gravitating mass: start {dark_frac[0]:.3f}, "
          f"collision {df_coll:.3f}, late {dark_frac[-1]:.3f}   (observed clusters ~0.83)")
    # outward = away from center along each side's travel axis: the observed
    # morphology is mass peaks OUTSIDE the central gas, so + = matches observation.
    out_lo = gas_lo_c[i_coll] - lens_lo_c[i_coll]
    out_hi = lens_hi_c[i_coll] - gas_hi_c[i_coll]
    for name, outw in (("LOW", out_lo), ("HIGH", out_hi)):
        if not np.isfinite(outw):
            print(f"  {name}: no lensing centroid on this side.")
        else:
            where = ("OUTWARD of" if outw > 0.25 else "INWARD of" if outw < -0.25
                     else "coincident with")
            print(f"  {name}: lensing centroid sits {outw:+.2f} cells {where} the gas centroid")
    if df_coll < 0.5:
        print(f"  VERDICT: dark mass is only {df_coll * 100:.0f}% of the total, so the lensing")
        print("  map tracks the GAS regardless of where the dimple sits -- the observed")
        print("  offset needs the dark component to dominate WHILE two halos still exist.")
    else:
        print(f"  VERDICT: dark mass dominates ({df_coll * 100:.0f}%) -- the lensing offsets")
        print("  above are now the real observable; + on both sides = Bullet-like.")
    if t_diss is not None:
        i_dom = np.nonzero(dark_frac >= 0.5)[0]
        if i_dom.size:
            t_dom = int(T[i_dom[0]])
            gap = "BEFORE" if t_dom <= t_diss else "AFTER"
            print(f"  timing: dark fraction first reaches 0.5 at t~{t_dom}, which is {gap} "
                  f"the halos dissolve (t~{t_diss}).")
        else:
            print(f"  timing: dark fraction never reaches 0.5 in this run "
                  f"(halos dissolve at t~{t_diss}).")

    # --- profile snapshot timesteps ---
    snaps = args.times if args.times else [tmin, t_coll, tmax]
    snap_labels = [f"t={s}" for s in snaps] if args.times \
        else ["start", f"collision (t={t_coll})", "late"]
    profiles = []
    maps2d = []
    for snap in snaps:
        s_real = min(ts_all, key=lambda x, snap=snap: abs(x - snap))
        profiles.append((s_real, col_profile(conn, run_id, s_real, ncol)))
        g2, d2 = grid2d(conn, run_id, s_real, ncol, nrow)
        maps2d.append((s_real, g2, d2, halo2d_metrics(g2, d2, mid, pct, args.halo_radius)))
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
        plot_a.axvline(t_diss, color=TAB_RED, ls="--", lw=1.0, label=f"halos dissolve (t~{t_diss})")
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
    plot_c.plot(T, clumped_frac, color=TAB_RED, lw=1.6, label="clumped fraction 1D (excess / total)")
    plot_c.plot(T, halo_frac2, "--", color=TAB_RED, lw=1.6, label="halo concentration 2D (disk / excess)")
    plot_c.plot(T, dark_frac, color=GREEN, lw=1.6, label="dark fraction of mass (dimple / total)")
    plot_c.plot(T, 0.5 * (np.asarray(dark_in_lo, float) + np.asarray(dark_in_hi, float)),
                "--", color=GREEN, lw=1.6, label="in-halo dark fraction 2D (mean of sides)")
    plot_c.axhline(0.5, color=GRAY, ls="--", lw=0.8)
    plot_c.axvline(t_coll, color=GRAY, ls=":", lw=1.0, label=f"collision (t={t_coll})")
    if t_diss is not None:
        plot_c.axvline(t_diss, color=TAB_RED, ls="--", lw=1.0, label=f"dissolve 1D (t~{t_diss})")
    if t_diss2 is not None:
        plot_c.axvline(t_diss2, color=TAB_RED, ls="-.", lw=1.0, label=f"dissolve 2D (t~{t_diss2})")
    plot_c.set_ylabel("clumped fraction", color=TAB_RED)
    plot_c.tick_params(axis="y", labelcolor=TAB_RED)
    plot_c.set_ylim(0, 1.02)
    plot_c.set_title("C. Halo coherence (red: 1D solid, 2D dashed) + dark fraction (green: "
                     "global solid, in-halo dashed) -- Bullet needs green high WHILE red is high",
                     fontsize=10, loc="left")
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
        lens = gas + dim
        lmax = lens.max() if lens.max() > 0 else 1.0
        plot_d.plot(cols, lens / lmax, color=GREEN, lw=1.8,
                    label="LENSING gas+dimple (norm)")
        plot_d.plot(cols, dim / dmax, color=PURPLE, lw=1.2, alpha=0.55, label="dimple raw (norm)")
        plot_d.plot(cols, exc / dmax, color=TAB_RED, lw=1.6, label="dimple excess (norm)")
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

    # --- figure 2: the 2D maps the metrics were computed from (ground truth) ---
    from matplotlib.patches import Circle
    fig2 = plt.figure(figsize=(12.5, 8))
    gs2 = gridspec.GridSpec(2, 3, hspace=0.30, wspace=0.25)
    fig2.suptitle(f"2D halo maps — Run {run_id}  (top: dimple + peak disks; "
                  f"bottom: LENSING gas+dimple, ^ = lensing peak, o = gas peak)",
                  fontsize=12)
    for j, (s_real, g2, d2, h2) in enumerate(maps2d):
        for r, field, cmap in ((0, d2, "magma"), (1, g2 + d2, "viridis")):
            ax = fig2.add_subplot(gs2[r, j])
            eps = field.max() * 1e-4 + 1e-30
            ax.imshow(np.log10(field + eps), origin="lower", cmap=cmap,
                      interpolation="nearest", aspect="equal")
            for side in ("LOW", "HIGH"):
                pr, pc = h2[side]["peak"]
                if r == 0:
                    ax.plot(pc, pr, "wx", ms=8, mew=2)
                    ax.add_patch(Circle((pc, pr), args.halo_radius, fill=False,
                                        color="white", ls="--", lw=1.0, alpha=0.8))
                else:
                    lr, lc = h2[side]["lens_peak"]
                    gr, gc = h2[side]["gas_peak"]
                    ax.plot(lc, lr, "^", color="cyan", ms=8, mew=1.5, mfc="none")
                    ax.plot(gc, gr, "o", color="lime", ms=8, mew=1.5, mfc="none")
            ax.axvline(mid, color="white", ls=":", lw=0.7, alpha=0.6)
            if r == 0:
                ax.set_title(f"{snap_labels[j]}  (dark-in: "
                             f"L {h2['LOW']['dark_in']:.2f} / H {h2['HIGH']['dark_in']:.2f})",
                             fontsize=9)
            ax.set_xlabel("col", fontsize=8)
            if j == 0:
                ax.set_ylabel("dimple (log)" if r == 0 else "lensing (log)", fontsize=9)
    out2 = OUTPUT_DIR / f"dimple_infall2d_run{run_id}.png"
    plt.savefig(out2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out2}")


if __name__ == "__main__":
    main()
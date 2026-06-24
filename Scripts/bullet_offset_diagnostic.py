"""
bullet_offset_diagnostic.py  (read-only)

The Bullet Cluster metric: per-clump displacement between the GAS (matter_density)
centroid and the DARK-MATTER DIMPLE (rip_dimple) centroid, measured along the
collision axis. Tolerant of halo overlap (Decision: success = centroid offset, not
disjoint halos).

Projection matches plot_lensing.py: sum each field along depth over non-BH cells ->
2D (row, col) surface density. Collision axis defaults to COL (= the WIDTH grid axis,
where BulletCluster offsets the pair).

TWO MEASUREMENT METHODS:
  peak     (default) -- locate each field's PEAK within the clump, then take a local
                        mass-weighted centroid in a small window around it. Ignores
                        the overlapping far tails, so it is NOT biased by the dimple
                        halo being broader than the gas. This is how real Bullet
                        Cluster analyses work (locate mass peaks), and it is robust
                        to the trailing bias a hard partition suffers.
  centroid          -- mass-weighted centroid of a hard spatial partition. Simple,
                        but a broader-than-gas dimple makes each half's dimple
                        centroid sit farther out than the gas centroid, biasing the
                        reading toward "trails". Kept for comparison only.

Why peak matters: bisecting a single broad clump with the centroid method reads a
false "dimple TRAILS gas" purely from the width difference (dimple sigma > gas sigma).
The peak method reads ~0 there, correctly, because the peaks are co-located.

Membership: clumps are separated along the collision axis. Default split is the
midplane; pass --centers A B (split at their midpoint) or --split S. After the clumps
cross, pass explicit --centers from the tracked cores.

Per clump: gas and dimple positions (by the chosen method) and signed offset
(dimple - gas) along the axis. Each clump moves toward the other (low side -> +axis,
high side -> -axis); "dimple LEADS gas" = dimple is farther along travel = the
Bullet Cluster signature.

Usage: py bullet_offset_diagnostic.py [--run-id 1] [--timestep N] [--axis col|row]
         [--method peak|centroid] [--window N] [--centers A B | --split S] [--db PATH]
"""
import argparse
import sqlite3
from pathlib import Path
import numpy as np

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"


def project(conn, run_id, ts, shape):
    gas = np.zeros(shape)
    dim = np.zeros(shape)
    for col, row, md, rd in conn.execute(
        """SELECT cp.col, cp.row, c.matter_density, c.rip_dimple
           FROM cell c JOIN cell_position cp ON c.cell_position_id = cp.cell_position_id
           WHERE c.run_id=? AND c.timestep=? AND c.is_black_hole=0""",
        (run_id, ts),
    ):
        gas[int(row), int(col)] += md
        dim[int(row), int(col)] += rd
    return gas, dim


def partition_centroid(grid, mask, ax):
    """Mass-weighted centroid of the hard-partitioned region along the axis."""
    region = np.where(mask, grid, 0.0)
    total = region.sum()
    if total <= 0:
        return float("nan")
    idx = np.indices(region.shape)[ax]
    return float((idx * region).sum() / total)


def peak_centroid(grid, mask, ax, window):
    """Local mass-weighted centroid in a window around the in-mask peak cell.
    Ignores overlapping far tails -> unbiased by halo width differences."""
    region = np.where(mask, grid, 0.0)
    if region.sum() <= 0:
        return float("nan")
    pr, pc = np.unravel_index(int(np.argmax(region)), region.shape)
    rlo, rhi = max(0, pr - window), min(grid.shape[0], pr + window + 1)
    clo, chi = max(0, pc - window), min(grid.shape[1], pc + window + 1)
    sub = region[rlo:rhi, clo:chi]
    if sub.sum() <= 0:
        return float("nan")
    idx = np.indices(sub.shape)[ax]
    local = (idx * sub).sum() / sub.sum()
    return float(local + (rlo if ax == 0 else clo))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=1)
    ap.add_argument("--timestep", type=int, default=None)
    ap.add_argument("--axis", choices=["col", "row"], default="col")
    ap.add_argument("--method", choices=["peak", "centroid"], default="peak")
    ap.add_argument("--window", type=int, default=6,
                    help="half-width (cells) of the local window for --method peak")
    ap.add_argument("--centers", type=float, nargs=2, default=None, metavar=("A", "B"))
    ap.add_argument("--split", type=float, default=None)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")
    conn = sqlite3.connect(db)

    ts = args.timestep
    if ts is None:
        ts = conn.execute("SELECT MAX(timestep) FROM cell WHERE run_id=?",
                          (args.run_id,)).fetchone()[0]
        if ts is None:
            raise SystemExit(f"No cell data for run_id={args.run_id}")
        ts = int(ts)

    mc, mr = conn.execute("SELECT MAX(col)+1, MAX(row)+1 FROM cell_position").fetchone()
    n_col, n_row = int(mc), int(mr)
    shape = (n_row, n_col)
    ax = 1 if args.axis == "col" else 0
    n_ax = n_col if args.axis == "col" else n_row

    gas, dim = project(conn, args.run_id, ts, shape)
    conn.close()

    if args.centers is not None:
        split = sum(args.centers) / 2.0
    elif args.split is not None:
        split = args.split
    else:
        split = n_ax / 2.0
    lo_dir, hi_dir = +1.0, -1.0

    coord = np.indices(shape)[ax]
    lo_mask = coord < split
    hi_mask = ~lo_mask

    def measure(grid, mask):
        if args.method == "peak":
            return peak_centroid(grid, mask, ax, args.window)
        return partition_centroid(grid, mask, ax)

    TOL = 1e-3
    print(f"\nrun {args.run_id}, timestep {ts}, grid {n_row}x{n_col}, "
          f"axis={args.axis}, method={args.method}"
          + (f", window={args.window}" if args.method == "peak" else "")
          + f", split={split:.2f}")
    leads_vals = []
    for name, mask, direction in (
        (f"clump LOW (moves +{args.axis})", lo_mask, lo_dir),
        (f"clump HIGH (moves -{args.axis})", hi_mask, hi_dir),
    ):
        gc = measure(gas, mask)
        dc = measure(dim, mask)
        if np.isnan(gc) or np.isnan(dc):
            print(f"  {name}: no mass on this side")
            leads_vals.append(None)
            continue
        signed = dc - gc
        leads = signed * direction
        leads_vals.append(leads)
        verdict = ("dimple LEADS gas" if leads > TOL else
                   "dimple TRAILS gas" if leads < -TOL else "co-located")
        print(f"  {name}:")
        print(f"      gas    = {gc:7.3f}")
        print(f"      dimple = {dc:7.3f}")
        print(f"      offset (dimple-gas) = {signed:+.3f}   "
              f"along travel = {leads:+.3f}  -> {verdict}")
    valid = [v for v in leads_vals if v is not None]
    print()
    if len(valid) < 2:
        print("  Inconclusive: need mass on both clumps.")
    elif all(v > TOL for v in valid):
        print("  >> Bullet Cluster SIGNATURE: dimple leads gas on BOTH clumps.")
    elif all(abs(v) <= TOL for v in valid):
        print("  >> NULL: gas and dimple co-located on both clumps (no offset).")
    elif all(v < -TOL for v in valid):
        print("  >> INVERTED: dimple trails gas on both clumps (unexpected).")
    else:
        print("  >> MIXED: clumps disagree -- check membership/split or timestep.")


if __name__ == "__main__":
    main()
"""
plot_stability.py  (read-only)

The tuning readout for GAS_SOUND_SPEED: max matter_density and max rip_dimple
(over NON-BH cells, so the 1e30 black-hole sentinel never distorts it) across the
whole run. A flat line means pressure is holding the gas; an upturn pinpoints the
Jeans-collapse blowup onset. Dial GAS_SOUND_SPEED until the line stays flat.

PERFORMANCE: samples timesteps explicitly (WHERE timestep=?) so each query uses the
(run_id, timestep) index and reads only the sampled timesteps. A "timestep % stride"
filter would instead force a full scan of every timestep in the run -- minutes on a
large DB. Larger --stride = fewer queries = faster.

Usage: py plot_stability.py [--run-id 1] [--stride 25] [--matter-ceiling 1e4] [--db PATH]
"""
import argparse
import sqlite3
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=1)
    ap.add_argument("--stride", type=int, default=25,
                    help="sample every Nth timestep (larger = faster)")
    ap.add_argument("--matter-ceiling", type=float, default=1e4,
                    help="reference line / blowup threshold for max matter_density")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")
    conn = sqlite3.connect(db)

    tr = conn.execute("SELECT MIN(timestep), MAX(timestep) FROM cell WHERE run_id=?",
                      (args.run_id,)).fetchone()
    if tr is None or tr[0] is None:
        raise SystemExit(f"No cell data for run_id={args.run_id}")
    tmin, tmax = int(tr[0]), int(tr[1])
    steps = list(range(tmin, tmax + 1, args.stride))
    if steps[-1] != tmax:
        steps.append(tmax)
    print(f"sampling {len(steps)} timesteps ({tmin}..{tmax}, stride {args.stride})")

    t, mmatter, mdimple = [], [], []
    for n, ts in enumerate(steps):
        row = conn.execute(
            """SELECT MAX(matter_density), MAX(rip_dimple) FROM cell
               WHERE run_id=? AND timestep=? AND is_black_hole=0""",
            (args.run_id, ts)).fetchone()
        if row is None or row[0] is None:
            continue
        t.append(ts); mmatter.append(row[0]); mdimple.append(row[1] or 0.0)
        if (n + 1) % 20 == 0 or n + 1 == len(steps):
            print(f"  ...{n + 1}/{len(steps)} timesteps", flush=True)
    conn.close()
    if not t:
        raise SystemExit(f"No cell data for run_id={args.run_id}")

    t = np.array(t); mmatter = np.array(mmatter); mdimple = np.array(mdimple)
    onset = None
    over = np.nonzero(mmatter > args.matter_ceiling)[0]
    if over.size:
        onset = int(t[over[0]])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle(f"Field stability — Run {args.run_id}"
                 + (f"   BLOWUP onset ~ t={onset}" if onset is not None
                    else "   (bounded — no blowup)"), fontsize=12)
    ax1.semilogy(t, np.maximum(mmatter, 1e-12), color="tab:red")
    ax1.axhline(args.matter_ceiling, ls="--", lw=0.8, color="gray",
                label=f"ceiling {args.matter_ceiling:g}")
    if onset is not None:
        ax1.axvline(onset, ls=":", color="black", lw=0.8)
    ax1.set_ylabel("max matter_density (non-BH, log)")
    ax1.legend(loc="upper left"); ax1.grid(True, which="both", alpha=0.3)
    ax2.plot(t, mdimple, color="tab:blue")
    if onset is not None:
        ax2.axvline(onset, ls=":", color="black", lw=0.8)
    ax2.set_ylabel("max rip_dimple (non-BH)"); ax2.set_xlabel("timestep")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    out = OUTPUT_DIR / f"stability_run{args.run_id}.png"
    plt.savefig(out, dpi=150); plt.close()
    print(f"max matter_density: {mmatter.min():.3g} .. {mmatter.max():.3g}")
    print(f"max rip_dimple:     {mdimple.min():.3g} .. {mdimple.max():.3g}")
    print("BLOWUP onset ~ t=" + str(onset) if onset is not None
          else "Field stayed bounded (no blowup).")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
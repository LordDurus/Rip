"""
sweep_param.py — sweep one app_setting over several values, appending a NEW run
per value into the EXISTING rip_data.db (no template reset), then tabulate each
run's first-pass gas-dimple offset.

How it stays in the existing DB: it invokes the sim with the RIP_APPEND env var
set, so `setup_database` keeps rip_data.db and adds a new run_id instead of
wiping and recopying template.db. Each parameter value is its own invocation
(= its own run_id), and the sim does exactly one run per invocation.

The template is only ever copied as a one-time bootstrap if rip_data.db does not
exist yet (or you pass --bootstrap for a clean sweep DB). Per-value runs never
reset. Each invocation produces exactly one run (the old NUM_RUNS loop is gone).

By default the sweep forces a t=0 collision (BULLET_KICK_RIP_RATE=0) so each
run collides immediately and short --timesteps suffice. Minimum timesteps is
set by the SLOWEST value: contact ~ initial_sep / (2*v*dt), plus roughly the
same again for the post-pass crest. At v=3, dt=0.01, sep~30 that is ~1000-1500
steps; faster values contact sooner. For a deliberate two-phase sweep pass
--keep-kick-mode and long --timesteps (the kick fires only after the epoch
cools, ~5k+).

Examples:
    # collision-velocity sweep (t=0 kick), post-pass offset per value
    py sweep_param.py --key BULLET_INITIAL_VELOCITY --values 3 6 9 12 \\
        --timesteps 1500 --sim-cmd "target\\release\\rip.exe"

    # sweep sound speed instead; pin momentum on
    py sweep_param.py --key GAS_SOUND_SPEED --values 1 2 4 \\
        --pin GAS_MOMENTUM_ENABLED=1 --sim-cmd "target\\release\\rip.exe"
"""
import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
# Derive ALL repo paths from the resolved root, not from a fixed
# parent.parent -- otherwise TEMPLATE points at the wrong place if the script
# ever moves relative to the repo root (DB_PATH already did this correctly).
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"
TEMPLATE = REPO / "data" / "template.db"
OUTPUT_DIR = REPO / "output"


def set_setting(conn, key, value):
    """Update one app_setting key; fail loud if it isn't there to update."""
    cur = conn.execute("UPDATE app_setting SET value=? WHERE key=?", (str(value), key))
    if cur.rowcount == 0:
        raise SystemExit(f"app_setting has no key '{key}' to set -- "
                         "is it seeded in template.db / rip_data.db?")
    conn.commit()


def get_setting(conn, key):
    row = conn.execute("SELECT value FROM app_setting WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def max_run_id(conn):
    row = conn.execute("SELECT MAX(run_id) FROM run").fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def run_status(conn, run_id):
    row = conn.execute("SELECT status FROM run WHERE run_id=?", (run_id,)).fetchone()
    return row[0] if row else None


def invoke_sim(sim_cmd):
    """Run the simulation in append mode. Returns (ok, tail_of_output)."""
    env = {**os.environ, "RIP_APPEND": "1"}
    proc = subprocess.run(sim_cmd, cwd=str(REPO), env=env, shell=True,
                          capture_output=True, text=True)
    tail = (proc.stdout or "")[-1500:] + (proc.stderr or "")[-1500:]
    return proc.returncode == 0, tail


def firstpass_json(run_id, timesteps, stride, window, post_pass=True):
    """Run the offset diagnostic in --json mode and return the parsed dict.

    post_pass=True measures the offset at the aftermath re-separation crest
    (where a Bullet offset is actually observable) rather than at closest
    approach (where the gas cores overlap and the offset washes out). The
    returned dict's "mode" field confirms which was used -- a sweep row
    showing mode=closest_approach means no clean crest was found and the
    number fell back, so read it with suspicion.
    """
    cmd = [sys.executable, str(SCRIPTS / "offset_firstpass.py"),
           "--run-id", str(run_id), "--coarse-stride", str(stride),
           "--max-timestep", str(timesteps), "--window", str(window),
           "--no-plot", "--no-trajectory", "--json"]
    if post_pass:
        cmd.append("--post-pass")
    r = subprocess.run(cmd, cwd=str(SCRIPTS), capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT_JSON "):
            return json.loads(line[len("RESULT_JSON "):])
    return None  # diagnostic produced no result (e.g. no cells)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", default="GAS_DRAG_COEFFICIENT", help="app_setting key to sweep (default: GAS_DRAG_COEFFICIENT).")
    ap.add_argument("--values", nargs="+", required=True, help="values to sweep, passed verbatim into app_setting.")
    ap.add_argument("--timesteps", type=int, default=1500, help="NUM_TIMESTEPS for each sweep run (default: 1500).")
    ap.add_argument("--offset-stride", type=int, default=5, help="coarse stride for the firstpass diagnostic (default: 5).")
    ap.add_argument("--offset-window", type=int, default=3, help="centroid window for the firstpass diagnostic (default: 3).")
    ap.add_argument("--pin", action="append", default=[], metavar="KEY=VALUE", help="also pin another setting for every run (repeatable).")
    ap.add_argument("--sim-cmd", default="cargo run --release",
                    help="command that runs the sim (default: 'cargo run --release'; "
                         "point at target\\release\\rip.exe to skip the build check).")
    ap.add_argument("--bootstrap", action="store_true",
                    help="copy template.db -> rip_data.db once before starting "
                         "(clean sweep DB). Otherwise append to the existing DB.")
    ap.add_argument("--keep-kick-mode", action="store_true",
                    help="do NOT force BULLET_KICK_RIP_RATE=0. By default the "
                         "sweep pins a t=0 kick so each short run collides "
                         "immediately; without this, a nonzero rate carried over "
                         "in the DB would make every run a delayed-kick run that "
                         "never fires in the sweep window (measuring pre-kick "
                         "drift). Only pass this for a deliberate two-phase sweep "
                         "with long --timesteps.")
    args = ap.parse_args()

    # Bootstrap only if asked, or if there's simply no DB to append to.
    if args.bootstrap or not DB_PATH.exists():
        why = "requested" if args.bootstrap else "rip_data.db absent"
        print(f"Bootstrapping rip_data.db from template ({why}; one-time, "
              "not per-run).")
        shutil.copy(TEMPLATE, DB_PATH)

    pins = {}
    for p in args.pin:
        if "=" not in p:
            raise SystemExit(f"--pin expects KEY=VALUE, got '{p}'")
        k, v = p.split("=", 1)
        pins[k.strip()] = v.strip()

    results = []
    for value in args.values:
        conn = sqlite3.connect(DB_PATH)
        try:
            set_setting(conn, args.key, value)
            set_setting(conn, "NUM_TIMESTEPS", args.timesteps)
            # Force an immediate (t=0) collision for the sweep unless the
            # user explicitly wants two-phase. Guards against a nonzero rate
            # left in the DB by a prior run turning every sweep run into a
            # delayed-kick that never fires in the short window.
            if not args.keep_kick_mode and args.key != "BULLET_KICK_RIP_RATE":
                set_setting(conn, "BULLET_KICK_RIP_RATE", "0")
            for k, v in pins.items():
                set_setting(conn, k, v)
            # Drag is inert without the momentum pass -- warn rather than silently
            # produce a null result.
            if args.key == "GAS_DRAG_COEFFICIENT" and get_setting(conn, "GAS_MOMENTUM_ENABLED") not in ("1", "true"):
                print("  WARNING: GAS_MOMENTUM_ENABLED is not on -- drag will do "
                      "nothing. Pin it: --pin GAS_MOMENTUM_ENABLED=1")
            before = max_run_id(conn)
        finally:
            conn.close()  # release the DB before the sim opens it

        print(f"\n=== {args.key} = {value}  ({args.timesteps} steps) ===")
        ok, tail = invoke_sim(args.sim_cmd)
        if not ok:
            print(tail)
            print(f"  sim FAILED for {args.key}={value}; skipping.")
            results.append({"value": value, "run_id": None, "status": "sim_failed"})
            continue

        conn = sqlite3.connect(DB_PATH)
        try:
            after = max_run_id(conn)
            status = run_status(conn, after)
        finally:
            conn.close()
        if after <= before:
            print(f"  no new run appeared (max_run_id stayed {before}); skipping.")
            results.append({"value": value, "run_id": None, "status": "no_run"})
            continue

        rid = after
        print(f"  -> run_id {rid} ({status})")
        data = firstpass_json(rid, args.timesteps, args.offset_stride,
                              args.offset_window)
        row = {"value": value, "run_id": rid, "status": status}
        if data:
            row.update(data)
        results.append(row)

    # --- comparison table ---
    print("\n" + "=" * 92)
    print(f"SWEEP RESULTS  ({args.key}, window +/-{args.offset_window})")
    print("=" * 92)
    hdr = (f"{'value':>10} {'run':>4} {'t_close':>8} {'min_sep':>8} "
           f"{'left_off':>9} {'right_off':>9} {'overlap':>8} {'note':>10}")
    print(hdr)
    print("-" * 92)
    for r in results:
        if r["run_id"] is None:
            print(f"{r['value']:>10} {'--':>4} {'--':>8} {'--':>8} "
                  f"{'--':>9} {'--':>9} {'--':>8} {r['status']:>10}")
            continue
        sep = r.get("separation", "?")
        lo = r.get("left_offset", "?")
        ro = r.get("right_offset", "?")
        ovl = "YES" if r.get("overlap") else "no"
        mode = r.get("mode", "?")
        note = "closest!" if mode == "closest_approach" else "post-pass"
        if r.get("used_fallback"):
            note = "GLOBALMIN"
        print(f"{r['value']:>10} {r['run_id']:>4} {r.get('timestep','?'):>8} "
              f"{sep:>8} {lo:>9} {ro:>9} {ovl:>8} {note:>10}")
    print("-" * 92)
    print("mode=post_pass is the aftermath re-separation crest (the real Bullet")
    print("sampling point). mode=closest_approach means no clean crest was found")
    print("and the row fell back to the overlapped collision -- treat its offset")
    print("as unreliable. overlap=YES (sep < 2*window) even in post_pass means the")
    print("clumps never cleanly separated: at low velocity they stay bound and")
    print("rattle in place -- that is a physical NULL (slow collisions make no")
    print("Bullet), not a window artifact. A real signature is a direction-")
    print("consistent gas-behind-dimple offset that GROWS with collision velocity.")

    # --- CSV for later use ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / f"sweep_{args.key}.csv"
    cols = ["value", "run_id", "status", "mode", "timestep", "separation",
            "initial_separation", "left_offset", "right_offset", "window",
            "overlap", "used_fallback"]
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"\nSaved table: {csv_path}")


if __name__ == "__main__":
    main()
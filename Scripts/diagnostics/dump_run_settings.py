"""Dump the run_setting snapshot for a run to stdout.

This is the ground-truth confirmation that the settings the simulation
*actually loaded* match what you intended -- the long-standing
config-propagation watch point. A key that exists in app_setting/source but
never made it into run_setting for this run did not reach the run, full stop.

Like bullet_offset_diagnostic.py and plot_stability.py, this prints to stdout
and lets the caller own the file. plot.bat redirects it:
    py dump_run_settings.py --run-id %run_id% >> %validation_file%
so the block lands in output/validation_run<run_id>.txt with everything else.

Defaults to the most recent completed run.

Examples:
    py dump_run_settings.py
    py dump_run_settings.py --run-id 7
    py dump_run_settings.py --run-id 7 --expect GAS_PRESSURE_ENABLED GAS_SOUND_SPEED
"""

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"

# Keys we currently insist on seeing in the snapshot. The active watch point is
# the thermal-pressure pair: if these are absent, the pressure path silently
# never ran no matter what the source says. Override with --expect.
DEFAULT_EXPECT = ["GAS_PRESSURE_ENABLED", "GAS_SOUND_SPEED"]


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


def run_header(conn, run_id):
    row = conn.execute(
        "SELECT started_at, ended_at, status, seed, git_commit, notes "
        "FROM run WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    started, ended, status, seed, commit, notes = row
    lines = [
        f"run_id     : {run_id}",
        f"status     : {status}",
        f"started_at : {started}",
        f"ended_at   : {ended}",
        f"seed       : {seed}",
        f"git_commit : {commit or '(none)'}",
    ]
    if notes:
        lines.append(f"notes      : {notes}")
    return lines


def load_settings(conn, run_id):
    rows = conn.execute(
        "SELECT key, value, datatype FROM run_setting "
        "WHERE run_id = ? ORDER BY key",
        (run_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(
            f"run_setting has NO rows for run_id={run_id}. The snapshot insert "
            "never ran -- this run's configuration was not recorded."
        )
    return rows


def main():
    print(f"Running: {os.path.basename(__file__)}")
    parser = argparse.ArgumentParser(description="Dump a run's run_setting snapshot for validation.txt.")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID to dump (default: most recent completed run).")
    parser.add_argument("--expect", nargs="*", default=DEFAULT_EXPECT,
                        help="Keys that MUST be present; missing ones are flagged. "
                             "Pass with no values to disable the check.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_id = resolve_run_id(conn, args.run_id)
        header = run_header(conn, run_id)
        settings = load_settings(conn, run_id)
    finally:
        conn.close()

    present = {k for k, _, _ in settings}
    missing = [k for k in args.expect if k not in present]

    width = max(len(k) for k, _, _ in settings)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    block = []
    block.append("=" * 72)
    block.append(f"RUN_SETTING SNAPSHOT  (dumped {stamp})")
    block.append("=" * 72)
    block.extend(header)
    block.append("-" * 72)
    block.append(f"{len(settings)} settings:")
    for key, value, datatype in settings:
        block.append(f"  {key:<{width}} = {value}    [{datatype}]")
    block.append("-" * 72)
    if not args.expect:
        block.append("expected-keys check: disabled")
    elif missing:
        block.append("*** MISSING EXPECTED KEYS (config did NOT propagate): "
                     + ", ".join(missing) + " ***")
    else:
        block.append("expected-keys check: OK -- all present ("
                     + ", ".join(args.expect) + ")")
    block.append("")

    text = "\n".join(block)
    print()
    print(text)

    # Fail loud so this can gate a script/batch: nonzero exit if a key is missing.
    # The MISSING banner is already in the printed block (and thus in the
    # validation file when redirected), so the failure is visible there too.
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
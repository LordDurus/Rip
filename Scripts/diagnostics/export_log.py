"""
Export the DB `log` table to a CSV that's easy to upload.

The Rust side writes log rows via `log_message` (timestamp is Unix epoch ms).
This pulls them back out, ordered chronologically, adds a readable UTC datetime
column, and writes one CSV per run into output/.

Usage:
  py export_log.py                      # latest run that has log rows
  py export_log.py --run-id 1
  py export_log.py --all                # every run, one file
  py export_log.py --min-level Warning  # only Warning + Error
  py export_log.py --output some.csv    # explicit path
"""
import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")
REPO = find_root()
DB_PATH = REPO / "data" / "rip_data.db"
OUTPUT_DIR = REPO / "output"

LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3}


def iso_utc(ts_ms):
    """Epoch milliseconds -> ISO-8601 UTC string. Falls back to raw on bad input."""
    try:
        return datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).isoformat(timespec="milliseconds")
    except (ValueError, OSError, OverflowError, TypeError):
        return ""


def resolve_run_id(conn, requested):
    if requested is not None:
        return int(requested)
    row = conn.execute("SELECT MAX(run_id) FROM log").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("No rows in the log table.")
    return int(row[0])


def main():
    ap = argparse.ArgumentParser(description="Export the DB log table to CSV.")
    ap.add_argument("--run-id", type=int, default=None, help="Run to export (default: latest run with log rows)")
    ap.add_argument("--all", action="store_true", help="Export every run instead of a single one")
    ap.add_argument("--min-level", default=None, help="Minimum severity: Debug|Info|Warning|Error")
    ap.add_argument("--output", default=None, help="Explicit output path (default: output/log_run{N}.csv)")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    min_rank = None
    if args.min_level is not None:
        min_rank = LEVEL_ORDER.get(args.min_level.lower())
        if min_rank is None:
            raise SystemExit(f"--min-level must be one of: Debug, Info, Warning, Error (got {args.min_level!r})")

    conn = sqlite3.connect(DB_PATH)

    where = []
    params = []
    if not args.all:
        run_id = resolve_run_id(conn, args.run_id)
        where.append("run_id = ?")
        params.append(run_id)
    sql = "SELECT id, timestamp, module, level, message, run_id FROM log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id ASC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if min_rank is not None:
        rows = [r for r in rows if LEVEL_ORDER.get(str(r[3]).lower(), 1) >= min_rank]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out = Path(args.output)
    elif args.all:
        out = OUTPUT_DIR / "log_all.csv"
    else:
        out = OUTPUT_DIR / f"log_run{run_id}.csv"

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "datetime_utc", "timestamp_ms", "run_id", "level", "module", "message"])
        for _id, ts, module, level, message, rid in rows:
            w.writerow([_id, iso_utc(ts), ts, rid, level, module, message])

    counts = {}
    for r in rows:
        counts[r[3]] = counts.get(r[3], 0) + 1
    by_level = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"
    print(f"Wrote {len(rows)} rows ({by_level})")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
retype_columns.py - Change the declared type of columns in a SQLite database,
in place, preserving comments. Generalizes the bool migration: give it
``table.column=TYPE`` specs and it swaps the declared type token via
writable_schema (safe - stored values are untouched, only the declared type /
affinity changes). Whitespace- and type-token-agnostic, so column-aligned DDL
and INT-vs-INTEGER differences don't matter.

Usage:
    python retype_columns.py template.db galaxy_timestep.radius=REAL \\
        galaxy_timestep.centroid_row=REAL galaxy_timestep.centroid_layer=REAL
    # add --apply to write (default is a dry run; makes a .bak)
"""

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# words that, if they show up where a type should be, mean the column is
# typeless (e.g. `centroid_col NOT NULL`) - swapping would corrupt it.
_NOT_A_TYPE = {"NOT", "NULL", "PRIMARY", "UNIQUE", "CHECK", "DEFAULT",
               "REFERENCES", "COLLATE", "GENERATED", "AS"}


def segment_spans(sql):
    n = len(sql)
    i = sql.find("(")
    if i < 0:
        return []
    i += 1
    depth, seg_start, spans = 1, i, []
    while i < n and depth > 0:
        ch = sql[i]
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            i = (n if j < 0 else j) + 2
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i + 2)
            i = n if j < 0 else j
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                spans.append((seg_start, i))
                break
        elif ch == "," and depth == 1:
            spans.append((seg_start, i))
            seg_start = i + 1
        i += 1
    return spans


def skip_leading(raw):
    i, n = 0, len(raw)
    while i < n:
        if raw[i].isspace():
            i += 1
        elif raw.startswith("/*", i):
            j = raw.find("*/", i + 2)
            i = (n if j < 0 else j + 2)
        elif raw.startswith("--", i):
            j = raw.find("\n", i + 2)
            i = (n if j < 0 else j)
        else:
            break
    return i


def split_comment(raw):
    positions = [p for p in (raw.find("/*"), raw.find("--")) if p != -1]
    if not positions:
        return raw, ""
    cut = min(positions)
    return raw[:cut], raw[cut:]


def first_identifier(raw):
    head = skip_leading(raw)
    m = re.match(r'[("`\[]*([A-Za-z_]\w*)', raw[head:])
    return m.group(1) if m else None


def rewrite_segment(raw, col, new_type, warnings, table):
    cstart = skip_leading(raw)
    lead = raw[:cstart]
    code, comment = split_comment(raw[cstart:])
    m = re.match(r"([A-Za-z_]\w*)(\s+)(\S+)(.*)$", code, re.S)
    if not m:
        warnings.append(f"{table}.{col}: could not parse definition, skipped")
        return None
    name, gap, old_type, rest = m.groups()
    if name != col:
        return None
    if old_type.upper() in _NOT_A_TYPE:
        warnings.append(
            f"{table}.{col}: looks typeless (next token '{old_type}'); "
            f"insert the type after the name instead, skipped")
        return None
    return f"{lead}{name}{gap}{new_type}{rest}{comment}"


def rewrite_table_ddl(sql, col_types, warnings, table):
    edits, done = [], set()
    for start, end in segment_spans(sql):
        raw = sql[start:end]
        name = first_identifier(raw)
        if name in col_types and name not in done:
            repl = rewrite_segment(raw, name, col_types[name], warnings, table)
            if repl is not None:
                edits.append((start, end, repl))
                done.add(name)
    for start, end, repl in sorted(edits, key=lambda x: x[0], reverse=True):
        sql = sql[:start] + repl + sql[end:]
    return sql, done


def probe_info(create_sql):
    c = sqlite3.connect(":memory:")
    try:
        renamed = re.sub(r"(CREATE\s+TABLE\s+)([\"`\[]?)\w+([\"`\]]?)",
                         r"\1_probe", create_sql, count=1, flags=re.IGNORECASE)
        c.execute(renamed)
        return {r[1]: r for r in c.execute("PRAGMA table_info(_probe)")}
    finally:
        c.close()


def structure_ok(old_sql, new_sql, changed):
    old, new = probe_info(old_sql), probe_info(new_sql)
    if set(old) != set(new):
        return False
    for name in old:
        o, n = old[name], new[name]
        if (o[0], o[1], o[3], o[4], o[5]) != (n[0], n[1], n[3], n[4], n[5]):
            return False
        if name not in changed and o[2] != n[2]:
            return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("specs", nargs="+", metavar="table.column=TYPE")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: {db_path} not found", file=sys.stderr)
        return 1

    by_table = {}
    for spec in args.specs:
        m = re.match(r"^(\w+)\.(\w+)=(.+)$", spec)
        if not m:
            print(f"error: bad spec '{spec}', want table.column=TYPE",
                  file=sys.stderr)
            return 1
        t, c, ty = m.groups()
        by_table.setdefault(t, {})[c] = ty.strip()

    conn = sqlite3.connect(db_path)
    table_sql = dict(conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table'"))
    warnings, plan, blocked = [], [], False
    for table, col_types in sorted(by_table.items()):
        if table not in table_sql:
            print(f"!! {table}: no such table")
            blocked = True
            continue
        new_sql, changed = rewrite_table_ddl(table_sql[table], col_types,
                                             warnings, table)
        missing = set(col_types) - changed
        for c in sorted(missing):
            print(f"!! {table}.{c}: not changed (see warnings)")
        if not changed:
            continue
        if not structure_ok(table_sql[table], new_sql, changed):
            print(f"!! {table}: rewrite altered structure, skipped")
            blocked = True
            continue
        plan.append((table, new_sql, changed))
        for c in sorted(changed):
            print(f"{table}.{c} -> {col_types[c]}")

    for w in warnings:
        print(f"  warning: {w}")
    if blocked:
        print("\nAborted: resolve the issues above and re-run.")
        conn.close()
        return 2
    if not plan:
        print("Nothing to change.")
        conn.close()
        return 0
    if not args.apply:
        print("\n(dry run - rerun with --apply to write)")
        conn.close()
        return 0

    backup = db_path.with_suffix(
        db_path.suffix + f".{datetime.now():%Y%m%d_%H%M%S}.bak")
    shutil.copy2(db_path, backup)
    print(f"\nbackup: {backup}")
    conn.execute("PRAGMA writable_schema=ON")
    for table, new_sql, _ in plan:
        conn.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
                     (new_sql, table))
    conn.execute("PRAGMA writable_schema=OFF")
    ver = conn.execute("PRAGMA schema_version").fetchone()[0]
    conn.execute(f"PRAGMA schema_version={ver + 1}")
    conn.commit()
    conn.close()
    chk = sqlite3.connect(db_path)
    status = chk.execute("PRAGMA integrity_check").fetchone()[0]
    chk.close()
    print(f"applied {len(plan)} table(s); integrity_check: {status}")
    return 0 if status == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
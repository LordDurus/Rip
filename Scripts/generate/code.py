"""Regenerate the data-driven regions of app_settings.rs from the app_setting table.

Single source of truth = app_setting in data/template.db. Rewrites two
marker-delimited regions in src/database/app_settings.rs:

  1. struct fields   between "// Begin generated properties" /
                             "// End generated properties"
  2. from_map fields between "// Begin setting generated properties" /
                             "// End setting generated properties"

Everything outside the markers is preserved byte-for-byte (CRLF kept).
Fields are emitted in alphabetical key order; descriptions become ///
doc comments (what you see on hover). Keys with an empty description are
reported on every run so gaps stay visible.

Do NOT put #[allow(dead_code)] on the AppSetting struct -- unused-field
warnings are the point of generating from the DB.

Workflow: add/rename/describe a setting in template.db, then run this.

Examples:
    py code.py
    py code.py --check     (exit 1 if app_settings.rs is stale; writes nothing)
"""

import argparse
import sqlite3
import sys
import textwrap
from pathlib import Path


def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")


REPO = find_root()
DEFAULT_DB = REPO / "data" / "template.db"
DEFAULT_CODE = REPO / "src" / "database" / "app_settings.rs"

STRUCT_BEGIN = "// Begin generated properties"
STRUCT_END = "// End generated properties"
MAP_BEGIN = "// Begin setting generated properties"
MAP_END = "// End setting generated properties"

# datatype column -> (rust type, from_map getter)
TYPE_MAP = {
    "f64": ("f64", "get_f64"),
    "usize": ("usize", "get_usize"),
    "u32": ("u32", "get_u32"),
    "u64": ("u64", "get_u64"),
    "bool": ("bool", "get_bool"),
    "text": ("String", "get_string"),
}

STRUCT_INDENT = "    "
MAP_INDENT = "            "
WRAP_COLS = 96


def load_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(app_setting)")}
        if "description" not in cols:
            raise SystemExit("app_setting has no description column -- run "
                             "extract_setting_descriptions.py first.")
        rows = conn.execute(
            "SELECT ltrim(rtrim(key)), ltrim(rtrim(datatype)), description "
            "FROM app_setting ORDER BY ltrim(rtrim(key))"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise SystemExit("app_setting is empty.")
    bad = [k for k, dt, _ in rows if dt not in TYPE_MAP]
    if bad:
        raise SystemExit(f"unknown datatype for key(s): {', '.join(bad)} "
                         f"(known: {', '.join(sorted(TYPE_MAP))})")
    return rows


def gen_struct_lines(rows):
    out = []
    for key, dtype, desc in rows:
        for line in textwrap.wrap(desc or "", WRAP_COLS - len(STRUCT_INDENT) - 4):
            out.append(f"{STRUCT_INDENT}/// {line}")
        rust_type, _ = TYPE_MAP[dtype]
        out.append(f"{STRUCT_INDENT}pub {key.lower()}: {rust_type},")
    return out


def gen_map_lines(rows):
    out = []
    for key, dtype, _ in rows:
        _, getter = TYPE_MAP[dtype]
        out.append(f"{MAP_INDENT}{key.lower()}: {getter}(\"{key}\"),")
    return out


def replace_region(text, begin, end, new_lines, nl):
    if begin not in text or end not in text:
        raise SystemExit(f"marker pair not found in app_settings.rs: "
                         f"{begin!r} / {end!r}")
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    marker_indent = head.rsplit(nl, 1)[-1] if nl in head else ""
    block = begin + nl + nl.join(new_lines) + nl + marker_indent + end
    return head + block + tail


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--code", type=Path, default=DEFAULT_CODE)
    ap.add_argument("--check", action="store_true",
                    help="Diff only: exit 1 if the file would change, write nothing.")
    args = ap.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")
    if not args.code.exists():
        raise SystemExit(f"Code file not found: {args.code}")

    rows = load_rows(args.db)

    missing = [k for k, _, d in rows if not (d or "").strip()]
    if missing:
        print(f"settings with NO description: {', '.join(missing)}")

    with open(args.code, encoding="utf-8", newline="") as f:
        original = f.read()
    nl = "\r\n" if "\r\n" in original else "\n"

    text = replace_region(original, STRUCT_BEGIN, STRUCT_END,
                          gen_struct_lines(rows), nl)
    text = replace_region(text, MAP_BEGIN, MAP_END, gen_map_lines(rows), nl)

    if text == original:
        print(f"{args.code.name}: up to date ({len(rows)} settings)")
        return

    if args.check:
        print(f"{args.code.name}: STALE -- regenerate (py code.py)")
        sys.exit(1)

    with open(args.code, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"{args.code.name}: regenerated both regions from {len(rows)} settings "
          f"in {args.db.name}")


if __name__ == "__main__":
    main()
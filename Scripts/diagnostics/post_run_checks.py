"""
post_run_checks.py  (read-only)

Post-run regression checks: one check per mechanism this project has validated
by hand, each emitting PASS / FAIL / WEIRD so a branch switch or template slip
(the GAS_PRESSURE_UPWIND=0 carryover) is caught by the next run's validation
file instead of a manual plot read.

Not unit tests: these read the completed run (rip_data.db + the run log) and
grade outcomes against behavior already validated in results.md.

Verdicts:
  PASS  -- matches validated behavior
  FAIL  -- regression relative to a validated mechanism
  WEIRD -- neither band: needs eyes. WEIRD is a first-class outcome; anything
           outside both bands is flagged, never silently binned.
  SKIP  -- check not applicable to this run's configuration

Thresholds are pre-registered from validated runs and noted per check;
PROVISIONAL thresholds (not yet pinned by a measured run) are marked in the
check's detail line so a WEIRD from them reads as calibration, not physics.

Usage: py post_run_checks.py [--run-id N] [--db PATH] [--template PATH]
Exit code: 1 if any FAIL, else 0.
"""
import argparse
import re
import sqlite3
from pathlib import Path

import numpy as np


def find_root(start=None, marker="Cargo.toml"):
    p = Path(start or __file__).resolve()
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise SystemExit(f"repo root not found: no {marker} at or above {p}")


def default_path(*parts):
    """Resolve repo-relative defaults lazily so explicit --db/--template work
    outside the repo tree (synthetic-DB validation, ad hoc copies)."""
    return find_root() / Path(*parts)

# Settings whose silent drift has caused (or would cause) misattributed runs.
CRITICAL_SETTINGS = [
    "GAS_PRESSURE_UPWIND",
    "GAS_MOMENTUM_ADVECTION",
    "BULLET_INITIAL_VELOCITY",
    "BULLET_KICK_RIP_RATE",
    "USE_DIMPLE_PARTICLES",
    "GAS_SOUND_SPEED",
    "SMBH_FORMATION_PROBABILITY",
    "GAS_DRAG_COEFFICIENT",
]

VERDICT_W = 5  # column width for verdict labels


class Report:
    def __init__(self):
        self.lines = []
        self.counts = {"PASS": 0, "FAIL": 0, "WEIRD": 0, "SKIP": 0}

    def add(self, verdict, name, detail):
        self.counts[verdict] += 1
        self.lines.append(f"  {verdict:<{VERDICT_W}} {name}: {detail}")

    def emit(self, run_id):
        print(f"POST-RUN CHECKS -- run {run_id}")
        for line in self.lines:
            print(line)
        c = self.counts
        print(f"SUMMARY: {c['PASS']} PASS, {c['FAIL']} FAIL, {c['WEIRD']} WEIRD, {c['SKIP']} SKIP")
        return 1 if c["FAIL"] else 0


# ---------------------------------------------------------------- schema help
def table_columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def find_table_with(conn, required_cols):
    """Locate a table containing all required columns; None if absent.
    Introspective on purpose: fails loud on schema drift instead of guessing."""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cols = set(table_columns(conn, t))
        if all(c in cols for c in required_cols):
            return t
    return None


def pick_col(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def resolve_run_id(conn, requested):
    if requested is not None:
        return requested
    row = conn.execute("SELECT MAX(run_id) FROM cell").fetchone()
    if row is None or row[0] is None:
        raise SystemExit("No runs found in cell table.")
    return int(row[0])


# ------------------------------------------------------------------- loaders
def load_run_settings(conn, run_id):
    """run_setting as {KEY: value-string}. Column names introspected."""
    table = find_table_with(conn, ["run_id", "value"])
    if table is None:
        return None, "no table with (run_id, value) columns found"
    cols = table_columns(conn, table)
    key_col = pick_col(cols, ["key", "name", "setting", "setting_key"])
    if key_col is None:
        return None, f"table {table} has no recognizable key column ({cols})"
    rows = conn.execute(
        f"SELECT {key_col}, value FROM {table} WHERE run_id=?", (run_id,)
    ).fetchall()
    return {str(k).upper(): str(v) for k, v in rows}, table


def load_template_settings(template_path):
    if not Path(template_path).exists():
        return None, f"template not found at {template_path}"
    tconn = sqlite3.connect(f"file:{template_path}?mode=ro", uri=True)
    try:
        rows = tconn.execute("SELECT key, value FROM app_setting").fetchall()
    finally:
        tconn.close()
    return {str(k).upper(): str(v) for k, v in rows}, "app_setting"


def load_log_messages(conn, run_id):
    """All log messages for the run, in id order. Table introspected: the one
    holding (run_id, level, message)."""
    table = find_table_with(conn, ["run_id", "level", "message"])
    if table is None:
        return None
    return [
        r[0]
        for r in conn.execute(
            f"SELECT message FROM {table} WHERE run_id=? ORDER BY rowid", (run_id,)
        )
    ]


def values_equal(a, b):
    """Setting comparison tolerant of numeric formatting (0.20 vs 0.2, 1 vs 1.0
    vs true). Falls back to case-insensitive string compare."""
    norm = {"true": "1", "false": "0"}
    a_n = norm.get(str(a).strip().lower(), str(a).strip().lower())
    b_n = norm.get(str(b).strip().lower(), str(b).strip().lower())
    try:
        return abs(float(a_n) - float(b_n)) < 1e-12
    except ValueError:
        return a_n == b_n


# -------------------------------------------------------------------- checks
def check_config_guard(rep, run_settings, template_settings):
    """FAIL on any critical setting mismatch between run_setting and
    template.db. A mismatch is either a template that didn't propagate or a
    deliberate override -- both deserve a loud line (this exact failure mode
    produced the GAS_PRESSURE_UPWIND=0 misattribution)."""
    if run_settings is None or template_settings is None:
        rep.add("WEIRD", "config_guard", "could not load settings (see loader notes above)")
        return
    mismatches, missing = [], []
    for key in CRITICAL_SETTINGS:
        rv, tv = run_settings.get(key), template_settings.get(key)
        if rv is None or tv is None:
            missing.append(f"{key} (run={rv}, template={tv})")
        elif not values_equal(rv, tv):
            mismatches.append(f"{key}: run={rv} template={tv}")
    if mismatches:
        rep.add("FAIL", "config_guard", "; ".join(mismatches))
    elif missing:
        rep.add("WEIRD", "config_guard", "missing keys: " + "; ".join(missing))
    else:
        rep.add("PASS", "config_guard", f"{len(CRITICAL_SETTINGS)}/{len(CRITICAL_SETTINGS)} critical settings match template")


BULK_RE = re.compile(r"t=(\d+): bulk_vel_w L=(-?\d+(?:\.\d+)?), R=(-?\d+(?:\.\d+)?)")
KICK_FIRED_RE = re.compile(r"t=(\d+): BULLET KICK fired")


def parse_bulk(messages):
    out = []
    for m in messages:
        g = BULK_RE.search(m)
        if g:
            out.append((int(g.group(1)), float(g.group(2)), float(g.group(3))))
    return out


def check_kick_rate_sanity(rep, run_settings):
    """Catch the recurring BULLET_KICK_RIP_RATE decimal slip (0.2 -> 0.02).
    Pre-registered value is 0.2; a nonzero rate below 0.1 fires the kick far
    too late and is almost always the dropped-zero typo, not intent."""
    raw = run_settings.get("BULLET_KICK_RIP_RATE")
    if raw is None:
        rep.add("SKIP", "kick_rate_sanity", "BULLET_KICK_RIP_RATE absent")
        return
    try:
        rate = float(raw)
    except ValueError:
        rep.add("WEIRD", "kick_rate_sanity", f"unparseable value {raw!r}")
        return
    if np.isclose(rate, 0.0):
        rep.add("SKIP", "kick_rate_sanity", "t=0 kick (rate 0) -- not two-phase")
    elif 0.0 < rate < 0.1:
        rep.add("WEIRD", "kick_rate_sanity",
                f"rate {rate} is below 0.1 -- likely the 0.2->0.02 decimal slip; "
                "kick will fire late on an over-cooled box")
    else:
        rep.add("PASS", "kick_rate_sanity", f"rate {rate} (>= 0.1)")


def check_kick_delivery(rep, run_settings, messages):
    """Bulk velocity at kick time must be ~ +/-BULLET_INITIAL_VELOCITY.
    Pre-registered from the validated smoke run (t=0 read 2.9985 on a 3.0
    kick, -0.05%): PASS within 2%, FAIL beyond 10% (clamp/zeroing bug)."""
    kick = float(run_settings.get("BULLET_INITIAL_VELOCITY", "0") or 0)
    if np.isclose(kick, 0.0):
        rep.add("SKIP", "kick_delivery", "BULLET_INITIAL_VELOCITY=0")
        return
    bulk = parse_bulk(messages)
    if not bulk:
        rep.add("WEIRD", "kick_delivery", "no bulk_vel_w lines in log (diagnostic removed?)")
        return
    rate = float(run_settings.get("BULLET_KICK_RIP_RATE", "0") or 0)
    delayed = rate > 0.0
    if delayed:
        fired = next((int(g.group(1)) for m in messages for g in [KICK_FIRED_RE.search(m)] if g), None)
        if fired is None:
            rep.add("SKIP", "kick_delivery", "delayed kick never fired (graded by kick_fired)")
            return
        sample = next(((t, l, r) for t, l, r in bulk if t >= fired), None)
    else:
        sample = bulk[0]
    if sample is None:
        rep.add("WEIRD", "kick_delivery", "no bulk_vel_w sample at/after kick time")
        return
    t, l, r = sample
    worst = max(abs(abs(l) - kick), abs(abs(r) - kick)) / kick
    # Delayed kicks tolerate more: the boost lands on a mature box and mixes
    # with existing internal motion before the diagnostic samples (measured
    # 2.8-3.3% across three two-phase runs), whereas an init kick on empty
    # cells reads ~0%. Widen PASS to 4% only for the delayed path.
    pass_band = 0.04 if delayed else 0.02
    detail = f"t={t}: L={l:.4f} R={r:.4f} vs +/-{kick} (worst {worst * 100:.2f}%)"
    if worst <= pass_band:
        rep.add("PASS", "kick_delivery", detail)
    elif worst > 0.10:
        rep.add("FAIL", "kick_delivery", detail + " -- clamp/zeroing suspected")
    else:
        rep.add("WEIRD", "kick_delivery", detail)


def check_momentum_decay(rep, run_settings, messages):
    """Post-kick decay must be gradual (drag/gravity/ledger mixing), never a
    cliff. Graded until |bulk| first falls below 50% of the kick (contact era
    begins; per-half accounting mixes after that). Pre-registered from the
    validated 7k run (worst single-step change well under 1%): PASS if max
    single-step drop < 5% of kick, FAIL if > 20% (something zeroed the field)."""
    kick = float(run_settings.get("BULLET_INITIAL_VELOCITY", "0") or 0)
    if abs(kick) < 1e-9:
        rep.add("SKIP", "momentum_decay", "BULLET_INITIAL_VELOCITY=0")
        return
    bulk = parse_bulk(messages)
    if len(bulk) < 3:
        rep.add("SKIP", "momentum_decay", "not enough bulk_vel_w samples")
        return
    worst = 0.0
    worst_t = None
    prev = None
    for t, l, r in bulk:
        mag = (abs(l) + abs(r)) / 2.0
        if prev is not None:
            drop = (prev - mag) / kick
            if drop > worst:
                worst, worst_t = drop, t
        if mag < 0.5 * kick:
            break
        prev = mag
    detail = f"worst single-step drop {worst * 100:.2f}% of kick" + (f" at t={worst_t}" if worst_t else "")
    if worst < 0.05:
        rep.add("PASS", "momentum_decay", detail)
    elif worst > 0.20:
        rep.add("FAIL", "momentum_decay", detail + " -- cliff, not physics")
    else:
        rep.add("WEIRD", "momentum_decay", detail)


def check_kick_fired(rep, run_settings, messages):
    """Two-phase runs must actually reach phase 2. FAIL if the epoch never
    cooled below the threshold on a run configured to collide."""
    rate = float(run_settings.get("BULLET_KICK_RIP_RATE", "0") or 0)
    kick = float(run_settings.get("BULLET_INITIAL_VELOCITY", "0") or 0)
    if rate <= 0.0 or abs(kick) < 1e-9:
        rep.add("SKIP", "kick_fired", "not a two-phase run")
        return
    fired = [m for m in messages if KICK_FIRED_RE.search(m)]
    never = [m for m in messages if "BULLET KICK never fired" in m]
    if fired:
        t = KICK_FIRED_RE.search(fired[0]).group(1)
        rep.add("PASS", "kick_fired", f"fired at t={t} (threshold {rate}/step)")
    elif never:
        rep.add("FAIL", "kick_fired", f"never fired: rip rate never dropped below {rate}/step")
    else:
        rep.add("WEIRD", "kick_fired", "no fire event and no never-fired notice in log")


# Tolerant of CSV-quoted lines and field order: capture each field by name
# independently rather than assuming a fixed left-to-right layout, so the
# check works whether messages come from the DB log column or an embedded
# CSV row. Non-greedy throughout.
TOTALS_T_RE = re.compile(r"t=(\d+):")
TOTALS_TD_RE = re.compile(r"total_dimple=([\d.eE+-]+)")
TOTALS_NP_RE = re.compile(r"dimple_particles=(\d+)")
TOTALS_PM_RE = re.compile(r"dimple_particle_mass=([\d.eE+-]+)")


def parse_totals(m):
    """Extract (t, total_dimple, n_particles, particle_mass) from a log line,
    or None if it is not a totals line. Field-independent so CSV quoting or
    reordering does not break it."""
    td = TOTALS_TD_RE.search(m)
    t = TOTALS_T_RE.search(m)
    if not td or not t:
        return None
    pm = TOTALS_PM_RE.search(m)
    npt = TOTALS_NP_RE.search(m)
    return (
        int(t.group(1)),
        float(td.group(1)),
        int(npt.group(1)) if npt else None,
        float(pm.group(1)) if pm else None,
    )


def check_particle_conservation(rep, run_settings, messages):
    """In particle mode the grid dimple IS the scattered particle mass:
    total_dimple == dimple_particle_mass at every sample. Divergence means the
    scatter-back loop is leaking (cap/budget-denominator family of bugs)."""
    if not values_equal(run_settings.get("USE_DIMPLE_PARTICLES", "0"), "1"):
        rep.add("SKIP", "particle_conservation", "USE_DIMPLE_PARTICLES=0")
        return
    worst = 0.0
    worst_t = None
    n = 0
    for m in messages:
        parsed = parse_totals(m)
        if parsed is None:
            continue
        t, total, _npart, pmass = parsed
        if pmass is None:
            continue  # line lacks particle mass -- cannot compare
        n += 1
        denom = max(abs(total), 1e-30)
        rel = abs(total - pmass) / denom
        if rel > worst:
            worst, worst_t = rel, t
    if n == 0:
        rep.add("WEIRD", "particle_conservation", "no totals lines parsed from log")
        return
    detail = f"{n} samples, worst |total_dimple - particle_mass| = {worst:.2e} rel" + (f" at t={worst_t}" if worst_t is not None else "")
    if worst < 1e-6:
        rep.add("PASS", "particle_conservation", detail)
    elif worst > 1e-3:
        rep.add("FAIL", "particle_conservation", detail)
    else:
        rep.add("WEIRD", "particle_conservation", detail)


def final_timestep(conn, run_id):
    row = conn.execute(
        "SELECT MAX(timestep) FROM cell WHERE run_id=?", (run_id,)
    ).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def check_checkerboard(rep, conn, run_id):
    """Odd-even (Nyquist) mode fraction in the final depth-summed gas map:
    A = |sum g(r,c) * (-1)^(r+c)| / sum |g - mean|. Central-difference pressure
    is blind to this mode; upwind damps it (validated A/B, results.md).
    Bands pinned from measured runs: clean upwind baseline 0.0080 (no
    collision), post-collision 0.0429 (shock injects some 2-cell structure,
    bounded, not growing per stability). PASS < 0.06 (clears post-collision),
    FAIL > 0.15 (plaid regression), WEIRD between."""
    t = final_timestep(conn, run_id)
    if t is None:
        rep.add("WEIRD", "checkerboard", "no cell data")
        return
    rows = conn.execute(
        """SELECT cp.col, cp.row,
                  SUM(CASE WHEN c.is_black_hole=0 THEN c.matter_density ELSE 0 END)
           FROM cell c JOIN cell_position cp ON c.cell_position_id=cp.cell_position_id
           WHERE c.run_id=? AND c.timestep=?
           GROUP BY cp.col, cp.row""",
        (run_id, t),
    ).fetchall()
    if not rows:
        rep.add("WEIRD", "checkerboard", f"no grid at t={t}")
        return
    ncol = max(r[0] for r in rows) + 1
    nrow = max(r[1] for r in rows) + 1
    g = np.zeros((nrow, ncol))
    for col, row, v in rows:
        g[int(row), int(col)] = v or 0.0
    fluct = g - g.mean()
    denom = np.abs(fluct).sum()
    if denom <= 0:
        rep.add("WEIRD", "checkerboard", f"flat field at t={t}")
        return
    signs = (-1.0) ** (np.add.outer(np.arange(nrow), np.arange(ncol)))
    frac = abs((fluct * signs).sum()) / denom
    detail = f"Nyquist fraction {frac:.4f} at t={t} (bands: pass<0.06, fail>0.15; clean=0.008, post-collision=0.043)"
    if frac < 0.06:
        rep.add("PASS", "checkerboard", detail)
    elif frac > 0.15:
        rep.add("FAIL", "checkerboard", detail + " -- plaid regression, check GAS_PRESSURE_UPWIND")
    else:
        rep.add("WEIRD", "checkerboard", detail)


def check_stability_bound(rep, conn, run_id, ceiling=10000.0):
    """Max non-BH matter density at the final sampled timestep vs the known
    blowup ceiling. PASS < 10% of ceiling, FAIL at/over ceiling."""
    t = final_timestep(conn, run_id)
    if t is None:
        rep.add("WEIRD", "stability_bound", "no cell data")
        return
    row = conn.execute(
        """SELECT MAX(c.matter_density) FROM cell c
           WHERE c.run_id=? AND c.timestep=? AND c.is_black_hole=0""",
        (run_id, t),
    ).fetchone()
    peak = float(row[0] or 0.0)
    detail = f"max non-BH density {peak:.3g} at t={t} (ceiling {ceiling:g})"
    if peak >= ceiling:
        rep.add("FAIL", "stability_bound", detail)
    elif peak < 0.1 * ceiling:
        rep.add("PASS", "stability_bound", detail)
    else:
        rep.add("WEIRD", "stability_bound", detail)


def check_epoch_tail(rep, run_settings, messages):
    """Informational thermometer: birth rate over the last two totals samples.
    WEIRD only on an impossible (negative) rate; otherwise PASS with the
    number, so every validation file records where the epoch stood."""
    if not values_equal(run_settings.get("USE_DIMPLE_PARTICLES", "0"), "1"):
        rep.add("SKIP", "epoch_tail", "USE_DIMPLE_PARTICLES=0")
        return
    samples = []
    for m in messages:
        parsed = parse_totals(m)
        if parsed is None:
            continue
        t, _total, npart, _pm = parsed
        if npart is not None:
            samples.append((t, npart))
    if len(samples) < 2:
        rep.add("WEIRD", "epoch_tail", "fewer than 2 totals samples")
        return
    (t0, n0), (t1, n1) = samples[-2], samples[-1]
    if t1 == t0:
        rep.add("WEIRD", "epoch_tail", "duplicate final sample timesteps")
        return
    rate = (n1 - n0) / (t1 - t0)
    if rate < 0:
        rep.add("WEIRD", "epoch_tail", f"negative birth rate {rate:.4f}/step -- impossible")
    else:
        rep.add("PASS", "epoch_tail", f"final birth rate {rate:.4f}/step ({n1} particles at t={t1})")


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--run-id", type=int, default=None)
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--template", type=Path, default=None)
    args = ap.parse_args()
    if args.db is None:
        args.db = default_path("data", "rip_data.db")
    if args.template is None:
        args.template = default_path("data", "template.db")

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    run_id = resolve_run_id(conn, args.run_id)
    rep = Report()

    run_settings, rs_note = load_run_settings(conn, run_id)
    template_settings, _ = load_template_settings(args.template)
    if run_settings is None:
        rep.add("WEIRD", "loader", f"run_setting: {rs_note}")
        run_settings = {}
    messages = load_log_messages(conn, run_id)
    if messages is None:
        rep.add("WEIRD", "loader", "no log table with (run_id, level, message) found")
        messages = []

    check_config_guard(rep, run_settings or None, template_settings)
    check_kick_rate_sanity(rep, run_settings)
    check_kick_delivery(rep, run_settings, messages)
    check_momentum_decay(rep, run_settings, messages)
    check_kick_fired(rep, run_settings, messages)
    check_particle_conservation(rep, run_settings, messages)
    check_epoch_tail(rep, run_settings, messages)
    check_checkerboard(rep, conn, run_id)
    check_stability_bound(rep, conn, run_id)

    raise SystemExit(rep.emit(run_id))


if __name__ == "__main__":
    main()
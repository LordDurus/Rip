#!/usr/bin/env python3
"""
generate_flowchart.py
Generates documents/architecture.md — a Mermaid flowchart of the Rip simulation.
Run automatically from plot.bat after each validated run.

Parses:
  src/create_data.rs              — timestep loop phases and active features
  src/galaxy.rs                   — galaxy lifecycle and active features
  src/database/sqlite_provider.rs — DB tables written each run

Do not edit architecture.md by hand; regenerate it with this script.
"""

import re
import sys
from pathlib import Path

# ── Locate repo root ──────────────────────────────────────────────────────────
script_dir = Path(__file__).parent
repo_root = script_dir
if not (repo_root / "src").exists():
    repo_root = script_dir.parent
if not (repo_root / "src").exists():
    print("ERROR: cannot find src/ directory. Run from repo root.", file=sys.stderr)
    sys.exit(1)

src = repo_root / "src"

def read(path): return path.read_text(encoding="utf-8")

def is_active(text, pattern):
    """True if pattern appears on at least one non-commented line."""
    for line in text.split('\n'):
        stripped = line.strip()
        if pattern in stripped and not stripped.startswith('//'):
            return True
    return False

# ── Parse files ───────────────────────────────────────────────────────────────
provider_text = read(src / "database" / "sqlite_provider.rs")
galaxy_text   = read(src / "galaxy.rs")
create_text   = read(src / "create_data.rs")

# Tables from INSERT INTO / UPDATE statements in sqlite_provider.rs
raw_tables = re.findall(
    r'(?:insert\s+into|INSERT\s+INTO|UPDATE\s+|update\s+)\s*(\w+)',
    provider_text
)
EXCLUDED = {"sqlite_sequence"}
tables = sorted(set(t for t in raw_tables if t not in EXCLUDED))

# Feature flags — check the file where each feature actually lives
discover_new_active      = is_active(create_text,  'Galaxy::discover_new')
process_mergers_active   = is_active(create_text,  'process_mergers(')
galaxy_drain_protection  = is_active(create_text,  'drain_factor')
star_gate_active         = is_active(create_text,  'star_formation_max_matter_delta')
baryonic_cap_active      = is_active(galaxy_text,  'baryonic_mass')

def yn(flag): return "✓ active" if flag else "✗ disabled"

# ── Mermaid: simulation loop ──────────────────────────────────────────────────
mermaid_loop = """graph TD
    A([Start Run]) --> B[Initialise Grid\\nbase geometry: Uniform / GaussianBlobs / Perlin / Custom]
    B --> C[place_galaxies\\nseed N galaxy regions at random positions]
    C --> D[apply_galaxy_overdensity\\nboost matter density inside galaxy regions]
    D --> E[seed_initial_curvature\\nper-cell curvature + galaxy curvature boost]
    E --> F[start_run\\nsnapshot app_setting → run_setting]
    F --> G[assign_run_id\\nstamp run_id onto seeded galaxies]
    G --> LOOP

    subgraph LOOP[" Timestep Loop "]
        direction TB
        L1[update_all_galaxies\\nPass 1 — tag cells + accumulate stats\\nPass 2 — update centroid + radius\\nPass 3 — apply SMBH baryonic cap]
        L1 --> L2

        subgraph L2[" Cell Update  parallel per cell "]
            direction TB
            L2a{{is_black_hole?}}
            L2a -->|SMBH| L2b[accretion\\nconnection_strength feed minus drain]
            L2a -->|normal BH| L2c[drain only\\nrevert if below collapse threshold]
            L2a -->|no| L2d{{matter_delta stable?\\nprev_delta < star_formation_max_matter_delta}}
            L2d -->|yes| L2e[star formation + extinction\\ndensity thresholds with hysteresis]
            L2d -->|no — too hot| L2f[extinction only\\nno new star formation]
            L2b --> L2g[galaxy drain protection\\n10x reduced drain if galaxy_id > 0]
            L2c --> L2g
            L2e --> L2g
            L2f --> L2g
        end

        L2 --> L3[compute_gravity_fft\\nFFT Poisson solver → gx gy gz per cell]
        L3 --> L4[apply_matter_transport\\nconservative matter redistribution]
        L4 --> L5[process_mergers\\noverlapping galaxies: smaller absorbed by larger]
        L5 --> L6[compute matter_delta\\nprevious_total_matter minus current_total_matter]
        L6 --> L7[update scale_factor\\nscale_factor × exp matter_delta × rate]
        L7 --> L8[save_all_cells → cell table]
        L8 --> L9[record_timestep_summary → timestep_summary table]
        L9 --> L10{{more timesteps?}}
        L10 -->|yes| L1
        L10 -->|no| DONE
    end

    DONE([complete_run])"""

# ── Mermaid: galaxy lifecycle ─────────────────────────────────────────────────
mermaid_galaxy = """graph TD
    G1([place_galaxies\\nN seeds at random positions\\nnegative placeholder ids]) --> G2
    G2[assign_run_id\\nafter start_run] --> G3
    G3[update_all_galaxies\\nevery timestep\\ncells tagged with galaxy_id] --> G4
    G4{{radius overlap\\nwith another galaxy?}}
    G4 -->|yes| G5[process_mergers\\nsmaller absorbed by larger\\nis_active = false]
    G4 -->|no| G6[grow radius\\nradius += total_mass × galaxy_mass_growth_rate]
    G5 --> G7([galaxy inactive])
    G6 --> G3"""

# ── Feature flags table ───────────────────────────────────────────────────────
flags_table = f"""| Feature | Status |
|---------|--------|
| Late-forming galaxy discovery (`discover_new`) | {yn(discover_new_active)} |
| Galaxy mergers (`process_mergers`) | {yn(process_mergers_active)} |
| Galaxy drain protection | {yn(galaxy_drain_protection)} |
| Star formation `matter_delta` gate | {yn(star_gate_active)} |
| SMBH baryonic mass cap | {yn(baryonic_cap_active)} |"""

# ── DB tables list ────────────────────────────────────────────────────────────
table_list = "\n".join(f"- `{t}`" for t in tables)

# ── Assemble ──────────────────────────────────────────────────────────────────
output = f"""# Rip Simulation — Architecture

> **Auto-generated** by `generate_flowchart.py` — do not edit by hand.  
> Regenerated automatically by `plot.bat` after each validated run.

## Simulation Loop

```mermaid
{mermaid_loop}
```

## Galaxy Lifecycle

```mermaid
{mermaid_galaxy}
```

## Database Tables

Tables written by `sqlite_provider.rs`:

{table_list}

## Active Feature Flags

{flags_table}
"""

out_path = repo_root / "documents" / "architecture.md"
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(output, encoding="utf-8")
print(f"Generated {out_path}")
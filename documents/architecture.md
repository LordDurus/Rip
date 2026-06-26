# Rip Simulation — Architecture

> **Auto-generated** by `generate_flowchart.py` — do not edit by hand.  
> Regenerated automatically by `plot.bat` after each validated run.

## Simulation Loop

```mermaid
graph TD
    A([Start Run]) --> B[Initialize Grid\nbase geometry: Uniform / GaussianBlobs / Perlin / Custom]
    B --> C[place_galaxies\nseed N galaxy regions at random positions]
    C --> D[apply_galaxy_overdensity\nboost matter density inside galaxy regions]
    D --> E[seed_initial_curvature\nper-cell curvature + galaxy curvature boost]
    E --> F[start_run\nsnapshot app_setting → run_setting]
    F --> G[assign_run_id\nstamp run_id onto seeded galaxies]
    G --> LOOP

    subgraph LOOP[" Timestep Loop "]
        direction TB
        L1[update_all_galaxies\nPass 1 — tag cells + accumulate stats\nPass 2 — update centroid + radius\nPass 3 — apply SMBH baryonic cap]
        L1 --> L2

        subgraph L2[" Cell Update  parallel per cell "]
            direction TB
            L2a{{is_black_hole?}}
            L2a -->|SMBH| L2b[accretion\nconnection_strength feed minus drain]
            L2a -->|normal BH| L2c[drain only\nrevert if below collapse threshold]
            L2a -->|no| L2d{{matter_delta stable?\nprev_delta < star_formation_max_matter_delta}}
            L2d -->|yes| L2e[star formation + extinction\ndensity thresholds with hysteresis]
            L2d -->|no — too hot| L2f[extinction only\nno new star formation]
            L2b --> L2g[galaxy drain protection\n10x reduced drain if galaxy_id > 0]
            L2c --> L2g
            L2e --> L2g
            L2f --> L2g
        end

        L2 --> L3[compute_gravity_fft\nFFT Poisson solver → gx gy gz per cell]
        L3 --> L4[apply_matter_transport\nconservative matter redistribution]
        L4 --> L5[process_mergers\noverlapping galaxies: smaller absorbed by larger]
        L5 --> L6[compute matter_delta\nprevious_total_matter minus current_total_matter]
        L6 --> L7[update scale_factor\nscale_factor × exp matter_delta × rate]
        L7 --> L8[save_all_cells → cell table]
        L8 --> L9[record_timestep_summary → timestep_summary table]
        L9 --> L10{{more timesteps?}}
        L10 -->|yes| L1
        L10 -->|no| DONE
    end

    DONE([complete_run])
```

## Galaxy Lifecycle

```mermaid
graph TD
    G1([place_galaxies\nN seeds at random positions\nnegative placeholder ids]) --> G2
    G2[assign_run_id\nafter start_run] --> G3
    G3[update_all_galaxies\nevery timestep\ncells tagged with galaxy_id] --> G4
    G4{{radius overlap\nwith another galaxy?}}
    G4 -->|yes| G5[process_mergers\nsmaller absorbed by larger\nis_active = false]
    G4 -->|no| G6[grow radius\nradius += total_mass × galaxy_mass_growth_rate]
    G5 --> G7([galaxy inactive])
    G6 --> G3
```

## Database Tables

Tables written by `sqlite_provider.rs`:

- `cell`
- `cell_position`
- `galaxy`
- `galaxy_timestep`
- `log`
- `run`
- `run_setting`
- `structure_particle`
- `timestep_summary`

## Active Feature Flags

| Feature | Status |
|---------|--------|
| Late-forming galaxy discovery (`discover_new`) | ✗ disabled |
| Galaxy mergers (`process_mergers`) | ✗ disabled |
| Galaxy drain protection | ✓ active |
| Star formation `matter_delta` gate | ✓ active |
| SMBH baryonic mass cap | ✓ active |

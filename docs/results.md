# Rip Simulation Results

A record of notable simulation results, the settings that produced them, and what they show. Unlike `run_log.md` (which tracks every tuning run), this document curates the results worth keeping and explaining.

---

## Inflation: Start, Expansion, and Graceful Exit

<img src="images/inflation_run1.png" alt="Inflation start/stop" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 500

### What it shows

This is the inflation signature produced by the rip field driving cosmic expansion.

**Top panel — Cosmic Expansion:** The scale factor climbs from 1 to roughly 10¹³ (about 30 e-folds of expansion), then flattens completely and holds steady. The expansion is driven by `compute_scale_factor`, which grows the scale factor each step while the rip-derived expansion factor stays above threshold.

**Bottom panel — Expansion Rate:** The growth rate `d(ln a)/dt` is the inflation signature. It ramps up rapidly, peaks early (~1000 Myr), then decays as the rip field weakens, and drops to zero at t ≈ 11,900 Myr. **Inflation ends** — the universe stops inflating and coasts.

### Why it matters

The defining challenge for any inflation model is the **graceful exit**: inflation must stop so that a normal, structure-forming universe can follow. A model that inflates forever cannot describe our universe. This run demonstrates a clean termination — expansion ramps, sustains for a finite epoch, then shuts off.

### Known limitations

The shutoff is currently a sharp discontinuity (growth rate drops from ~0.0005 to 0 in a single timestep) rather than a smooth dynamical rolloff. This is an artifact of the hard `expansion_factor > 0.05` cutoff in `compute_scale_factor`. A future refinement could replace the hard threshold with a smooth rolloff for a more physically realistic exit.

---

## Cosmic Microwave Background Analog

### Matter Density Fluctuations

<img src="images/cmb_power_run1_matter_density_t147.png" alt="CMB-analog matter density power spectrum" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 147 &nbsp;|&nbsp; **Field:** matter_density (non-black-hole cells only)

### What it shows

**Left panel — Fluctuation Map:** Large-scale overdense (red) and underdense (blue) regions are clearly visible after black hole cells are excluded. The structure reflects the Perlin noise initial conditions evolved through accretion and gravitational dynamics. Coherent blobs spanning 10–20 cells are visible, consistent with the Perlin correlation length set by `PERLIN_FREQUENCY = 0.05`.

**Right panel — Power Spectrum:** A clean steep power law from k=1 to k~30, declining roughly four decades in power. More power at large scales (low k) than small scales (high k) — the expected signature of correlated initial conditions. No acoustic peaks are present, which is expected since the simulation has no baryon-photon oscillator.

### Known limitations

- Black hole cells are excluded and replaced with the non-BH mean for the FFT — col/row positions where all depth layers are black holes contribute no real signal.
- The power law slope reflects the Perlin seeding more than dynamical evolution at this timestep; a later timestep after more accretion may show more structure.
- The `matter_density` field is not mass-conserving — accretion adds matter locally without transferring it from neighbors.

---

## Matter Loss and Expansion (Phase 1 — in progress)

*(pending — testing whether total_matter drain correlates with the scale factor expansion rate)*

---

## Large-Scale Structure

### 2D Matter Density Map

<img src="images/structure_run1_t2000.png" alt="Large-scale structure at timestep 2000" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 2000 &nbsp;|&nbsp; **Field:** matter_density (non-BH cells only)

### What it shows

**Left panel — Matter Density Projection:** The maximum matter density along the depth axis projected onto a 2D map. Overdense regions (yellow/orange) are clearly separated by underdense voids (black). The structure reflects gravitational accretion acting on Perlin noise initial conditions over 2000 timesteps, with the rip drain progressively removing matter from all cells. Distinct dense nodes and filament-like connections between them are visible.

**Right panel — Density Distribution:** The matter density histogram at t=2000 with the filament (top 30%) and void (bottom 30%) thresholds marked. The distribution is unimodal — a consequence of the uniform rip drain acting on all cells equally. Real cosmic structure would show a more bimodal distribution as gravity amplifies overdensities over longer timescales.

### 3D Interactive Visualization

**[Open interactive 3D view](structure_3d_run1_t2000.html)** — rotate, zoom, and explore the black hole and matter density distribution in three dimensions.

<img src="images/structure_3d_run1_t2000.png" alt="3D structure at timestep 2000" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 2000 &nbsp;|&nbsp; **Density percentile:** top 5%

### What it shows

High-density matter cells (colored by density, Plasma colorscale) and black hole positions (cyan) rendered in 3D. Black holes are clearly concentrated in the same regions as high-density matter rather than randomly distributed — consistent with gravitational collapse driving black hole formation in overdense regions. Distinct clustering is visible with emptier regions between clumps.

### Known limitations

- Structure at t=2000 is heavily influenced by the rip drain — matter density has fallen to ~2% of its peak value, so the contrast between overdense and underdense regions is compressed.
- The 64³ grid is too coarse to resolve filament width reliably — a 512³ production run would show much finer structure.
- Accretion is local (no mass transfer between cells), so filaments form from initial Perlin overdensities amplified by gravity rather than from true matter flow along filaments.
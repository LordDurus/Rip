# Rip Simulation Results

A record of notable simulation results, the settings that produced them, and what they show. Unlike `run_log.md` (which tracks every tuning run), this document curates the results worth keeping and explaining.

---

## Inflation: Contraction, Expansion, and a Smooth Graceful Exit

<img src="images/inflation_run1.png" alt="Inflation start/stop" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 200

### What it shows

This is the inflation signature produced by **matter loss driving cosmic expansion**. `compute_scale_factor` was rewired from the earlier abstract rip formula to grow the scale factor in response to matter leaving the budget — drained through rips and sequestered into black holes (excluded from `total_matter`).

**Top panel — Cosmic Expansion:** The scale factor starts at 1.0, dips a couple percent below 1.0 (a brief early contraction while accretion outpaces the still-dormant rips), then turns over and climbs smoothly to ~1.30, where it plateaus and holds. The total expansion follows directly from how much matter is lost: because each step multiplies `a` by `exp(matter_delta · MATTER_EXPANSION_RATE)`, the relationship telescopes to `a(t) = exp(MATTER_EXPANSION_RATE · [M₀ − M(t)])`. The plateau at ~1.3 corresponds to nearly the entire initial matter budget having drained.

**Bottom panel — Expansion Rate:** `d(ln a)/dt` is the inflation signature. It opens with a brief negative excursion (the contraction), spikes positive as the rips activate, eases into a smooth hump (peak ~2×10⁻⁵ near 4,000 Myr), then decays to zero on its own as the matter drain exhausts. **Inflation ends** because there is nothing left to drain — a self-terminating exit at t ≈ 20,300 Myr.

### Why it matters

The defining challenge for any inflation model is the **graceful exit**: inflation must stop so a normal, structure-forming universe can follow. This run terminates cleanly — and, unlike the earlier formula-driven version, the shutoff is now a **smooth dynamical rolloff** rather than a hard cutoff. The growth rate tapers to zero as the drain runs out, not because a threshold trips.

The early **contraction** is a new feature, revealed once the artificial `max(1.0)` floor on the scale factor was removed. Before the rips activate, accretion briefly wins, matter grows, and the universe contracts ~2%; the bottom of that dip is the physics-driven onset of expansion. Contraction-before-expansion is well-trodden ground in cosmology (bouncing/cyclic models, going back to Tolman 1934), though here it arises from the matter-budget bookkeeping rather than from GR dynamics.

### Known limitations

- The expansion is modest (~1.3×, ~0.26 e-folds) at `MATTER_EXPANSION_RATE = 1e-6` — it is bounded by the available matter budget (`exp(k · M₀)`). A larger rate scales the e-folds up.
- The scale factor is currently a **passive diagnostic**: it records the `a(t)` implied by matter loss but does not feed back to dilute densities (no ρ ∝ a⁻³). Expansion and structure are decoupled in the current model.
- *(Superseded.)* The earlier "hard discontinuity at `expansion_factor > 0.05`" limitation no longer applies — that cutoff and the abstract rip formula were replaced by the matter-loss mechanism.

---

## Matter Loss Drives Expansion

### What it shows

The scale factor is wired directly to matter leaving the budget. Because the per-step update is multiplicative-exponential, `a(t) = exp(MATTER_EXPANSION_RATE · cumulative_matter_lost)` holds exactly. The expansion at any time is therefore an analytic function of how much matter has been removed from normal spacetime — the correlation is not approximate, it is built in by construction. The substantive question is the *shape* of `total_matter(t)`, which is what gives the inflationary profile its form.

### Why it matters

This is the core hypothesis of the project: matter crossing into rips and black holes, removed from normal spacetime, is what drives expansion. The run shows the mechanism produces an inflation-like `a(t)` with a graceful exit emerging from the physics rather than imposed by a formula.

---

## Cosmic Microwave Background Analog

### Matter Density Fluctuations

<img src="images/cmb_power_run1_matter_density_t200.png" alt="CMB-analog matter density power spectrum" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 200 &nbsp;|&nbsp; **Field:** matter_density (non-black-hole cells only)

### What it shows

**Left panel — Fluctuation Map:** Large-scale overdense (red) and underdense (blue) regions are clearly visible. The structure reflects the Perlin-noise initial conditions evolved through accretion and gravitational dynamics, with coherent blobs spanning 10–20 cells consistent with the Perlin correlation length.

**Right panel — Power Spectrum:** A clean steep power law from k=1 to k~30, declining roughly four decades in power. More power at large scales (low k) than small scales (high k) — the expected signature of correlated initial conditions. No acoustic peaks are present, as expected for a simulation with no baryon–photon oscillator.

### Known limitations

- Black hole cells are excluded from the field; col/row positions where all depth layers are black holes contribute no real signal.
- The slope reflects the Perlin seeding as much as dynamical evolution; matter_density is denser at t=200 than at late times because the rip drain has not yet stripped it.
- The `matter_density` field is not mass-conserving — accretion adds matter locally without transferring it from neighbors.

### Curvature and Rip Strength

The `curvature` and `rip_strength` fields are noise-dominated by contrast: both spectra fall off the k=1 mode and flatten into a white-noise floor with no long-range coherence. This is expected — these fields are set locally, whereas `matter_density` is the only field acted on directly by the FFT gravity solver, so it is the only one that develops large-scale structure.

---

## Large-Scale Structure

### 2D Matter Density Map

<img src="images/structure_run1_t200.png" alt="Large-scale structure at timestep 200" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 200 &nbsp;|&nbsp; **Field:** matter_density (non-BH cells only)

### What it shows

**Left panel — Matter Density Projection:** The maximum matter density along the depth axis projected onto a 2D map. Overdense regions (yellow/orange) are separated by underdense voids (dark), with distinct dense nodes and filament-like connections between them. The structure is gravitational accretion acting on the Perlin initial conditions.

**Right panel — Density Distribution:** The histogram at t=200 with filament (top 30%, ~0.128) and void (bottom 30%, ~0.087) thresholds marked. The distribution is unimodal — a consequence of the roughly uniform drain acting on all cells. Real cosmic structure would show a more bimodal distribution as gravity amplifies overdensities over longer timescales.

### 3D Interactive Visualization

**[Open interactive 3D view](structure_3d_run1_t200.html)** — rotate, zoom, and explore the matter density distribution in three dimensions.

<img src="images/structure_3d_run1_t200.png" alt="3D structure at timestep 200" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 200 &nbsp;|&nbsp; **Density percentile:** top 5%

### What it shows

High-density matter cells (colored by density, Plasma colorscale) rendered in 3D, with clear clustering and emptier regions between clumps — consistent with gravitational collapse concentrating matter in overdense regions.

### Known limitations

- The 64³ grid is too coarse to resolve filament width reliably — a 512³ production run would show much finer structure.
- Accretion is local (no mass transfer between cells), so filaments form from initial Perlin overdensities amplified by gravity rather than from true matter flow along filaments.

---

## Black Hole Reversal (added — verification pending)

Black holes can now relax back into ordinary cells once they drain below half their formation threshold (with hysteresis), the counterpart to formation. A dedicated `bh_drain_rate` acts as the clock that sets black-hole lifetime; on reversal the residual matter re-enters `total_matter`, which is intended to register as a contraction. The goal is to turn the single early contraction into a train of contract/expand cycles, with the matter budget shrinking each cycle.

**Status:** The current inflation curve (Run 1, 200 timesteps) does **not** yet show clear multi-cycle oscillation — only the single opening dip, with one small kink in the growth rate near 6,500 Myr. Whether reversal is firing but desynchronized, or not firing at all, is being verified directly from the `black_hole_count` time series in `timestep_summary` (a count that rises *and falls* confirms reversal). This section will be completed once that is confirmed.

---

## Notes on This Run

- Two correctness fixes preceded this run: a copy-paste bug that doubled `scale_factor_avg`/`rip_strength_avg` in the timestep summary, and the removal of the `max(1.0)` floor on the scale factor (which had been hiding the early contraction).
- The `1e30` black-hole sentinel for `matter_density` was removed; black hole cells now carry their real matter, which is what makes reversal accounting and a clean gravity FFT possible.

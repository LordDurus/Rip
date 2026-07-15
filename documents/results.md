# Rip Simulation Results

A record of notable simulation results, the settings that produced them, and what they show. Unlike `run_log.md` (which tracks every tuning run), this document curates the results worth keeping and explaining.

---

## Inflation: Contraction, Expansion, and a Smooth Graceful Exit

<img src="images/inflation_run1.png" alt="Inflation start/stop" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 2000

### What it shows

This is the inflation signature produced by **matter loss driving cosmic expansion**. `compute_scale_factor` was rewired from the earlier abstract rip formula to grow the scale factor in response to matter leaving the budget — drained through rips and sequestered into black holes (excluded from `total_matter`).

**Top panel — Cosmic Expansion:** The scale factor starts at 1.0, dips a couple percent below 1.0 (a brief early contraction while accretion outpaces the still-dormant rips), then turns over and climbs smoothly to ~1.30, where it plateaus and holds. The total expansion follows directly from how much matter is lost: because each step multiplies `a` by `exp(matter_delta · MATTER_EXPANSION_RATE)`, the relationship telescopes to `a(t) = exp(MATTER_EXPANSION_RATE · [M₀ − M(t)])`. The plateau at ~1.3 corresponds to nearly the entire initial matter budget having drained.

**Bottom panel — Expansion Rate:** `d(ln a)/dt` is the inflation signature. It opens with a brief negative excursion (the contraction), spikes positive as the rips activate, eases into a smooth hump (peak ~2×10⁻⁵ near 4,000 Myr), then decays to zero on its own as the matter drain exhausts. **Inflation ends** because there is nothing left to drain — a self-terminating exit at t ≈ 20,300 Myr.

### Why it matters

The defining challenge for any inflation model is the **graceful exit**: inflation must stop so a normal, structure-forming universe can follow. This run terminates cleanly — and, unlike the earlier formula-driven version, the shutoff is now a **smooth dynamical rolloff** rather than a hard cutoff. The growth rate tapers to zero as the drain runs out, not because a threshold trips.

The early **contraction** is a new feature, revealed once the artificial `max(1.0)` floor on the scale factor was removed. Before the rips activate, accretion briefly wins, matter grows, and the universe contracts ~2%; the bottom of that dip is the physics-driven onset of expansion. Contraction-before-expansion is well-trodden ground in cosmology (bouncing/cyclic models, going back to Tolman 1934), though here it arises from the matter-budget bookkeeping rather than from GR dynamics.

### Epistemic note: this result was not targeted

The inflation-like profile was not an explicit design goal. The simulation was built to model matter crossing geometric thresholds into child geometries. The scale factor was wired to respond to matter loss. The inflation shape — rapid early expansion, smooth deceleration, graceful exit — fell out without tuning for it.

This matters for evaluating the hypothesis. Standard inflation theory was constructed backwards: the inflaton field was invented specifically to produce the flatness, horizon-agreement, and monopole-dilution observations. A mechanism designed to reproduce observations is weak evidence for those observations. Rip's inflation-like curve was unsolicited. It emerges from one rule applied identically across all epochs (matter loss expands spacetime), producing epoch-appropriate behavior — fast early, slow late — without separate physics for each epoch. That unification is a stronger signal than a purpose-built fit would be.

See `decisions.md` — *Emergent inflation-like behavior as epistemic signal* — for the full principle.

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

<img src="images/cmb_power_run1_matter_density_t0.png" alt="CMB-analog matter density power spectrum" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 2000 &nbsp;|&nbsp; **Field:** matter_density (non-black-hole cells only)

### What it shows

**Left panel — Fluctuation Map:** Large-scale overdense (red) and underdense (blue) regions are clearly visible. The structure reflects the Perlin-noise initial conditions evolved through accretion and gravitational dynamics, with coherent blobs spanning 10–20 cells consistent with the Perlin correlation length.

**Right panel — Power Spectrum:** A clean steep power law from k=1 to k~30, declining roughly four decades in power. More power at large scales (low k) than small scales (high k) — the expected signature of correlated initial conditions. No acoustic peaks are present, as expected for a simulation with no baryon–photon oscillator.

### Known limitations

- Black hole cells are excluded from the field; col/row positions where all depth layers are black holes contribute no real signal.
- The slope reflects the Perlin seeding as much as dynamical evolution; matter_density is denser at t=2000 than at late times because the rip drain has not yet stripped it.
- The `matter_density` field is not mass-conserving — accretion adds matter locally without transferring it from neighbors.

### Curvature and Rip Strength

The `curvature` and `rip_strength` fields are noise-dominated by contrast: both spectra fall off the k=1 mode and flatten into a white-noise floor with no long-range coherence. This is expected — these fields are set locally, whereas `matter_density` is the only field acted on directly by the FFT gravity solver, so it is the only one that develops large-scale structure.

---

## Large-Scale Structure

### 2D Matter Density Map

<img src="images/structure_run1_t2000.png" alt="Large-scale structure at timestep 2000" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 2000 &nbsp;|&nbsp; **Field:** matter_density (non-BH cells only)

### What it shows

**Left panel — Matter Density Projection:** The maximum matter density along the depth axis projected onto a 2D map. Overdense regions (yellow/orange) are separated by underdense voids (dark), with distinct dense nodes and filament-like connections between them. The structure is gravitational accretion acting on the Perlin initial conditions.

**Right panel — Density Distribution:** The histogram at t=2000 with filament (top 30%, ~0.128) and void (bottom 30%, ~0.087) thresholds marked. The distribution is unimodal — a consequence of the roughly uniform drain acting on all cells. Real cosmic structure would show a more bimodal distribution as gravity amplifies overdensities over longer timescales.

### 3D Interactive Visualization

**[Open interactive 3D view](structure_3d_run1_t2000.html)** — rotate, zoom, and explore the matter density distribution in three dimensions.

<img src="images/structure_3d_run1_t2000.png" alt="3D structure at timestep 2000" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timestep:** 2000 &nbsp;|&nbsp; **Density percentile:** top 5%

### What it shows

High-density matter cells (colored by density, Plasma colorscale) rendered in 3D, with clear clustering and emptier regions between clumps — consistent with gravitational collapse concentrating matter in overdense regions.

### Known limitations

- The 64³ grid is too coarse to resolve filament width reliably — a 512³ production run would show much finer structure.
- Accretion is local (no mass transfer between cells), so filaments form from initial Perlin overdensities amplified by gravity rather than from true matter flow along filaments.

---

## Black Hole Reversal (added — verification pending)

Black holes can now relax back into ordinary cells once they drain below half their formation threshold (with hysteresis), the counterpart to formation. A dedicated `bh_drain_rate` acts as the clock that sets black-hole lifetime; on reversal the residual matter re-enters `total_matter`, which is intended to register as a contraction. The goal is to turn the single early contraction into a train of contract/expand cycles, with the matter budget shrinking each cycle.

**Status:** The current inflation curve (Run 1, 2000 timesteps) does **not** yet show clear multi-cycle oscillation — only the single opening dip, with one small kink in the growth rate near 6,500 Myr. Whether reversal is firing but desynchronized, or not firing at all, is being verified directly from the `black_hole_count` time series in `timestep_summary` (a count that rises *and falls* confirms reversal). This section will be completed once that is confirmed.

---

## Notes on This Run

- Two correctness fixes preceded this run: a copy-paste bug that doubled `scale_factor`/`rip_strength_avg` in the timestep summary, and the removal of the `max(1.0)` floor on the scale factor (which had been hiding the early contraction).
- The `1e30` black-hole sentinel for `matter_density` was removed; black hole cells now carry their real matter, which is what makes reversal accounting and a clean gravity FFT possible.

---

### Matter transport and structure formation

Conservative two-pass, gravity-driven matter transport (`helpers/transport.rs`) replaced the
broken non-conservative accretion term. With `transport_rate = 0.025`, matter clusters under its
own gravity into a cosmic web — filaments, nodes, and voids — with a red (large-scale-weighted)
matter power spectrum. Higher rates (0.05) over-concentrate into isolated spikes. Transport is a
**one-way concentrator**: matter only flows downhill, so the rate sets the *timescale* of clumping,
not its final degree.

### Black-hole formation is transport-sustained

The earlier "Black holes created: 0" was a *survivor* count at the final timestep, not a cumulative
count. True arc: a synchronized formation wave at t=0, a synchronized reversal wave as those holes
drain below threshold (early, ~t≈7000 Myr in the inflation plot), then settling. Without transport,
the count drops to zero and stays there. With transport, surviving matter re-clusters and
re-collapses, so the population persists (re-formation).

### Headline result: a(t) responds to the black-hole channel only when the diffuse drain is subdominant

a(t) = exp(k · matter_lost). With the diffuse rip drain at `rip_drain_rate = 1.25e-6` (effective
~1.2%/cell/step after ×rip_strength), the leak dominates the matter budget and a(t) is
**byte-identical across every configuration** (transport on/off, web/spikes, holes/none) — a smooth
monotonic ramp to ~1.3. The leak is a *one-way* channel, so a(t) is monotonic by construction and no
black-hole dynamics can bend it.

Lowering `rip_drain_rate` to `1.25e-8` (~100×) puts the black-hole channel in charge of the matter
budget. Result (64³, 500 steps):

- ~5114 black holes survive to t=499 (vs 19 under the strong drain), core densities ~430.
- a(t) breaks from the ~1.3 ramp down to ~1.058 and, critically, shows a **contraction** —
  d(ln a)/dt goes negative — coinciding with the first reversal wave.

This is the first demonstration that the reversal channel can bend a(t) negative: matter into holes
expands a(t), matter re-injected from reverting holes contracts it. The core mechanism, on screen.

**Caveat:** one pulse, not a sustained cycle. After the first synchronized wave the population
de-phases (cells form and revert at staggered times) and a(t) settles into a gentle climb. Sustained
cycling needs a re-synchronizing driver, not a parameter tweak (see ideas-to-explore).

**Reproducing recipe:** `transport_rate = 0.025`, `rip_drain_rate = 1.25e-8`, curvature = random
seed (`rng 0.0..0.1`), `curvature_threshold = 0.08`, `collapse_density_threshold = 1.5`, accretion
removed, gravity write-back active, straight axis pairing.
---

## Phase 1 Confirmed: Matter Loss Correlates with Expansion

<img src="images/matter_run1.png" alt="Total matter vs scale factor" width="600">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 5000

### What it shows

A direct plot of `total_matter` (non-BH cells only, left axis) against `scale_factor` (right axis) over the full run. The two curves are mirror images: as matter falls into black holes and leaves normal spacetime, the scale factor rises in lockstep.

Key features:

- **Early spike (t < 2000):** The initial BH formation wave drives a sharp drop in total matter and a corresponding fast rise in scale factor — the bulk of the expansion happens here.
- **Matched deceleration:** Both curves flatten at the same rate after ~t=1000, consistent with expansion being driven by the *rate* of matter loss — as d(matter)/dt slows, so does d(a)/dt.
- **Clean anti-correlation throughout:** The relationship holds across all 5000 timesteps without divergence or anomaly.

### Why it matters

This is the Phase 1 hypothesis test: does matter loss from normal spacetime correlate with expansion? The answer is unambiguous — yes, and the shape of the correlation is exactly what the mechanism predicts. The scale factor is not being driven by an abstract formula; it tracks the matter budget directly.

This result justifies proceeding to Phase 2: rewiring `compute_scale_factor` to use −d(total_matter)/dt as its direct input, replacing the current per-cell average.

### Next step

Phase 2 — rewire `compute_scale_factor` to derive expansion rate from `−d(total_matter)/dt` computed from `timestep_summary`, making the matter-loss-drives-expansion mechanism explicit rather than implicit.
---

## Supermassive Black Holes: Heavy-Tailed Overmassive Population from Threshold-Crossing

<img src="images/smbh_run1_t4999.png" alt="SMBH mass distribution and connection-strength relationship" width="700">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 5000 &nbsp;|&nbsp; **Mode:** `tied_to_curvature`

### What it shows

This targets the JWST anomaly of overmassive early black holes — black-hole-to-stellar-mass ratios of 10–30% at high redshift versus ~0.1–0.5% locally — where instantaneous threshold-crossing collapse has a natural edge over slow accretion. SMBHs form from rare high-curvature seeds that cross a higher threshold than ordinary black holes (`smbh_curvature_threshold`), with formation probability biased toward early timesteps (`exp(−t / smbh_early_bias)`). Once formed, each SMBH feeds from the parent geometry at its own **connection strength**, drawn heavy-tailed at formation: most SMBHs get a near-zero feed and stall near drain-balance; a rare few get a strong connection and run away to overmassive scale. Persistence is a consequence of net-positive growth (connection exceeding `bh_drain_rate`), not an imposed exemption from reversal.

**Left panel — mass distribution:** A textbook heavy tail. A large spike of stalled SMBHs sits near the formation floor, with a long declining tail stretching across many orders of magnitude to the runaway giants. The population is overwhelmingly small holes with a rare overmassive minority — qualitatively the JWST regime, where most black holes are unremarkable and a few are anomalously large for their epoch.

**Right panel — connection strength versus mass, colored by formation curvature:** A sharp threshold at the drain rate (~10⁻²): below it every SMBH is stalled flat along the mass floor, above it mass climbs near-vertically. The runaway points are uniformly high-curvature (bright), while the stalled floor is mixed — the visual signature of the curvature-mass correlation that the `tied_to_curvature` mode produces.

### The two connection modes are empirically distinguishable

The connection-strength assignment is a pluggable mode (`SmbhConnectionMode`), allowing the curvature-tied and independent hypotheses to be compared directly. Splitting SMBHs into runaway (mass > 1000) and stalled groups and comparing their formation curvature:

| Mode | Runaway curvature | Stalled curvature | Correlation |
|------|-------------------|-------------------|-------------|
| `tied_to_curvature`  | 0.0989 | 0.0974 | present |
| `independent_draw`   | 0.0975 | 0.0975 | absent |

In the curvature-tied mode the SMBHs that ran away are those that formed in deeper curvature wells; in the independent mode the giants and the stalled holes are drawn from the same curvature distribution. Both modes produce the same heavy-tailed overmassive population, so the JWST anomaly itself does not distinguish them — but the curvature-mass correlation does.

### Why it matters

The mechanism reproduces the qualitative JWST signature without slow accretion: instantaneous threshold-crossing plus a rare strong parent-geometry feed produces overmassive holes early and fast. More usefully, the mode comparison yields a **falsifiable observational test**: under the rip hypothesis with curvature-tied connection, observed SMBH masses should correlate with the curvature of their formation environment; under independent connection, they should not. This is checkable in principle against the relationship between SMBH mass and host-galaxy/halo properties.

### Known limitations

- **Unbounded growth — resolved (galaxy-phase2).** Runaway SMBH mass was previously unbounded, reaching ~10¹⁶ as the competitive cap was defeated by a double-subtraction in its denominator (the budget shrank to zero as an SMBH grew, removing its own cap — see `decisions.md`). With that fixed, in-galaxy SMBH mass is bounded by the per-galaxy baryonic budget and the population tops out near ~10⁶, a heavy-tailed distribution with no runaway spike. The conservation question (the parent-inflow term creating matter within the single modeled geometry) remains open and is recorded separately in `decisions.md`.
- **Population count — partially resolved (galaxy-phase2).** The *in-galaxy* population is now ≈1 SMBH per galaxy via emergent mass-dominance merging (see the galaxy section above). The raw seed count remains high (~9,000–12,000) because ~95% of SMBHs form as orphans outside any galaxy; these are self-limiting but not yet reduced to a realistic count. Tying SMBH *formation* (not just in-galaxy merging) to a rarer condition or to galaxy structures is the remaining step toward a fully realistic total.
- **No feedback to structure.** As with the inflation result, SMBH mass does not yet feed back into the gravity field or dilute surrounding densities.

### Next step

The galaxy branch is now implemented (see the galaxy section above): FoF galaxies self-assemble from the density field, and emergent mass-dominance merging produces ≈1 SMBH per galaxy. The open threads from here are the orphan SMBH population (~95% of seeds, self-limiting but high-count), tying SMBH *formation* to host properties to bring the raw count toward realism, and the SMBH↔structure rip-feedback question (mass feeding back into the gravity field).
## Galaxies: Emergent One-SMBH-per-Galaxy from Friends-of-Friends Structure

<img src="images/galaxy_run1.png" alt="Galaxy centroid map, early vs late timestep" width="700">

**Run:** 1 &nbsp;|&nbsp; **Grid:** 64×64×64 &nbsp;|&nbsp; **Timesteps:** 5000 &nbsp;|&nbsp; **FoF threshold:** 5.0 &nbsp;|&nbsp; **SMBH dominance threshold:** 0.5

### What it shows

Galaxies are no longer seeded. Each post-inflation timestep, a friends-of-friends (FoF) finder identifies galaxies fresh from the density field: connected components of cells above the linking density, re-derived every step, with identity carried forward only by cell-overlap matching. A galaxy is a gravitationally-linked collection of matter, not a placed object — its membership, mass, centroid, and radius are pure functions of the current field.

**Galaxy count is hierarchical.** Many small galaxies condense just after inflation (~220 at the first post-inflation snapshot), then merge and drain into fewer, larger ones over time (~80 at the midpoint, ~10–15 by the end). This birth-then-merge trajectory is emergent from the drain-and-merge dynamics, not imposed.

**One dominant SMBH per galaxy emerges.** Within each FoF region, SMBHs compete for a shared baryonic budget (a per-SMBH cap) and merge gradually: the most massive SMBH is the winner, and any SMBH below half the winner's mass is absorbed into it, mass conserved. The result across the full run is an average of ≈1 SMBH per galaxy, with a maximum of 2–3 in any single galaxy early (transient post-merger pairs) falling to 1 late. The centroid map shows this directly: early galaxies carry a spread of SMBH counts (colored), late galaxies are almost uniformly single-SMBH (one color). This is achieved with no "keep only one" rule — it falls out of the FoF region definition plus a mass-keyed gradual merge.

### Why it matters

This converts the earlier high raw SMBH seed count into a realistic galaxy-scale population. Real galaxies overwhelmingly host a single central supermassive black hole, with occasional dual AGN caught in the window between a galaxy merger and the coalescence of the two black holes. The simulation reproduces exactly that: ≈1 per galaxy, with rare transient duals during merger events — and it does so emergently, from a single competition rule applied to self-assembling structures, rather than by construction.

### Known limitations

- **Orphan SMBHs dominate the raw count.** ~95% of SMBHs form outside any FoF galaxy (in voids and filaments) and are not subject to the in-galaxy competition. They are self-limiting (their growth is tied to local curvature, which is low in drained regions, so they plateau near ~10⁶ rather than running away) but they are not part of the one-per-galaxy result, which governs only the in-galaxy population. Whether orphans should exist at this fraction is an open physical question, documented in `decisions.md`.
- **Merge target is not physically unique.** The winner is chosen by mass; since the absorbed mass is conserved into it, the choice of winner has no observable consequence (the merged remnant is identical either way), but it means "which SMBH survives" is a bookkeeping convention, not a physical prediction.
- **No SMBH→structure feedback yet.** The dominant SMBH's mass still does not feed back into the surrounding density field or gravity.

## Gas checkerboard A/B: upwind pressure gradient (bullet-cluster-phase1)

**Question.** Is the odd-even (checkerboard) gas instability the upstream cause of the gas antipode migration (t~900) and the DM halo dissolution (2D t~1425)?

**Setup.** Two 7,000-step runs, byte-identical settings (seed 8, `SMBH_FORMATION_PROBABILITY=0`, `USE_DIMPLE_PARTICLES=1`), single variable: `GAS_PRESSURE_UPWIND` (velocity-signed one-sided pressure gradient vs. original central differences). Settings confirmed in `run_setting` via `dump_run_settings.py` for both runs.

**Result.**

| Metric | upwind = 1 | upwind = 0 (control) |
|---|---|---|
| Late matter density map | clean two-clump, bounded residual plaid at low-density outskirts | full checkerboard takeover |
| Gas antipode migration | none (centroids ~13-16 cells all run) | returns at t~900 (jump to ~35) |
| 2D halo verdict | SURVIVES to t=6999 (concentration 0.73) | DISSOLVES at t~1425 (concentration 0.17) |
| Lensing peak vs gas peak | 0.0 / 0.0 (clean, honestly zero) | 8.2 / 72.0 (corner corruption) |
| Dimple particles at end | 12,067 (still trickling) | 29,507 (frozen at t~3600) |
| Total dimple at end | 2,140 (rising +4.5% final quarter) | 4,700 (plateaued) |
| Dark fraction (global / in-halo) | 0.113 / 0.15-0.16 | 0.245 / 0.42-0.43 |

**Verdict.** Causal chain confirmed: checkerboard -> gas antipode migration -> halo dissolution. The central-difference pressure gradient is blind to the 2-cell odd-even mode (grad = 0 exactly at a checkerboard extremum); donor-cell advection sources noise at that wavelength and FFT gravity is Nyquist-blind, so the mode had a source and no sink. The upwind stencil couples adjacent cells and provides the sink.

**Secondary finding.** The previously celebrated "first clean epoch completion" (birth zero at t~3600, 29,507 particles) was substantially artifact-fed: checkerboard density spikes triggered spurious collapse, manufacturing ~2x the dimple mass and exhausting the birth pool early. With clean gas, rip births continue slowly past t=7,000 (genuine collapse as gas condenses, max density 10 -> 53). The control's higher dark fraction (0.245 vs 0.113) is artifact-sourced dimple, not better physics. Epoch-completion criteria must be re-established on clean-gas runs.

**Follow-ups.** (1) Passive infall will not produce a collision: separation 30.0 -> 25.5 cells over 7,000 steps, decelerating (pressure-supported near-equilibrium + periodic-image pull + expansion). Act-three two-phase design needs an initial velocity kick (issue #19). (2) Dark fraction 0.11 vs observed ~0.83 is the standing composition gap. (3) Residual bounded plaid at low-density outskirts is the expected first-order-upwind equilibrium; not growing per stability check.

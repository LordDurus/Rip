# Design Decisions

A record of non-obvious choices made during development, and the reasoning behind them.
This is distinct from `RESULTS.md` (which records what the simulation produced) and
`run_log.md` (which tracks parameter tuning). This document records *why* the code
is the way it is.

---

## Physics & Model

### Inertia is intrinsic, not emergent (Machian)
**Decision:** Treat inertia as a fixed property of matter rather than emerging from
the gravitational relationship with all other matter in the universe (Mach's principle).

**Reason:** Machian inertia would require computing each particle's effective inertia
as a function of the full matter distribution every timestep — high implementation cost
with negligible observable difference at current simulation scales. The standard
assumption in most physics is intrinsic inertia. This is the conservative choice.

**Consequence:** Matter carried beyond gravitational reach during inflation coasts
forever and is permanently lost — the universe has a leaky boundary. Each cycle of
expansion starts with slightly less total matter than the last.

**Revisit:** See `ideas-to-explore.md` — Machian inertia section.

---

### Symmetric matter delta drives expansion
**Decision:** Both matter loss and matter gain affect the scale factor symmetrically.
Matter loss → expansion, matter gain → contraction. The scale factor has a floor of
its initial value (cannot un-exist) but no ceiling.

**Reason:** Using only matter loss (`.max(0.0)` on the delta) would bias the hypothesis
test — the scale factor could only ever increase, making the matter-loss-drives-expansion
correlation trivially true regardless of the actual physics. A symmetric test is the
honest one. During the inflation epoch matter loss dominates anyway, so expansion still
wins — but the test is fair.

---

### Emergent inflation-like behavior as epistemic signal

**Observation:** The simulation was not designed to produce inflation. The mechanism — matter crossing geometric thresholds into child geometries, removing itself from normal spacetime — was built to model black hole formation. When the scale factor was wired to respond to matter loss, an inflation-like profile emerged without targeting it: rapid early expansion driven by peak-density rip rates, smooth deceleration as the drain exhausts, graceful exit with no engineered cutoff.

**Why this matters for the hypothesis:** Inflation as standardly formulated was constructed *backwards* — the inflaton field was invented specifically to produce flatness, horizon-agreement, and monopole dilution. Its fit to those observations is therefore weak evidence; a mechanism designed to fit will fit. Rip's inflation-like behavior was not solicited. The shape emerged from a single rule applied uniformly across all epochs: matter lost from normal spacetime expands it. That the same rule produces inflation-scale behavior early (when densities and rip rates are highest) and slow late-time expansion afterward — without separate physics for each epoch — is a stronger signal than a mechanism that was tuned to do so.

**The structural argument:** Standard inflation requires different physics at different epochs (inflaton-dominated early, radiation/matter-dominated later, dark-energy-dominated now). Rip uses one rule throughout. Unification across epochs with emergent epoch-appropriate behavior is the more parsimonious outcome. The flatness and horizon problems that inflation was invented to solve also have a natural candidate answer here: if matter under extreme early-universe density bleeds off into rips rather than accumulating enough to reverse expansion, the rip mechanism acts as a pressure-release valve that naturally drives the geometry toward flatness without requiring a separate inflaton field.

**Principle recorded here:** When a simulation produces a result it was not tuned to produce, that is a higher-quality signal than a result it was designed for. The inflation profile belongs in this category. Future results should be evaluated on the same criterion.

---

### FFT Poisson solver for gravity (Jeans swindle for k=0)
**Decision:** Solve ∇²φ = 4πGρ in Fourier space using three 1D FFT passes per axis
with periodic boundary conditions. The k=0 mode (mean density) is set to zero — the
"Jeans swindle."

**Reason:** The k=0 mode corresponds to the gravitational effect of the entire
universe on itself, which diverges in an infinite uniform medium. Setting it to zero
is standard practice in cosmological N-body simulations and avoids an unphysical
infinite self-gravity term. Periodic boundaries are chosen over zero-padded because
the simulation models a representative volume of the universe, not an isolated system
in empty space.

---

### Rip drain is symmetric with accretion
**Decision:** Each non-BH cell gains matter via accretion (proportional to local
gravity magnitude) and loses matter via rip drain (proportional to local rip strength).
Neither term is clamped to prevent the other from winning.

**Reason:** The competition between accretion and drain is the physical mechanism
being tested. Artificially preventing drain from winning would bias the result. The
rates (`ACCRETION_RATE`, `RIP_DRAIN_RATE`) are tunable parameters — the simulation
finds its own equilibrium.

---

### Black hole matter density sentinel value (1e30)
**Decision:** When a cell collapses into a black hole, `matter_density` is set to
`1e30` as a sentinel value rather than tracking actual accreted mass.

**Reason:** Black hole interiors are excluded from all field calculations and
`total_matter` summation. The sentinel makes BH cells easy to identify and filter.
True mass tracking inside black holes is deferred until black hole healing
(`RipDecayMechanism::SelfHealing`) is implemented, at which point the return path
for matter needs a physically motivated value.

---

## Implementation

### `apply_gravity_interaction` removed
**Decision:** The function that coupled `matter_density` and `curvature` locally
each timestep was removed entirely.

**Reason:** This was a pre-FFT placeholder from before the Poisson gravity solver
was implemented. After the FFT solver was added, the function became a phantom
coupling that ran on top of real gravity, causing `matter_density` to grow
monotonically every timestep regardless of physical conditions. It was not replaced
— the FFT solver is the complete gravity implementation.

---

### `RipDecayMechanism::Diffusive` panics by design
**Decision:** The `Diffusive` variant of `RipDecayMechanism` panics with a clear
message rather than silently doing nothing.

**Reason:** Silent no-ops in enum variants are dangerous — they produce wrong results
without any indication that something is unimplemented. A loud failure is preferable
until the mechanism is actually implemented.

---

### Accretion is local, not mass-conserving
**Decision:** The accretion term adds matter to high-gravity cells without removing
it from neighbors. Matter is created locally rather than transferred.

**Reason:** True mass-conserving accretion requires computing flux between adjacent
cells — a more complex implementation. Local accretion is a deliberate simplification
that captures the qualitative behavior (over dense regions get denser) without the
full machinery. Noted as a known limitation in `RESULTS.md`.

---

## Tuning History

### Why `RIP_DRAIN_RATE = 1.25e-6`
Starting from `1e-6` (no turnover in 5000 timesteps) and `1e-3` (matter drained
to zero by t=3), binary search converged on `1.25e-6` as producing a clean peak
around t=32 with ~35% of peak matter remaining at t=500 and stable black hole
count. This is the first value that produced a meaningful turnover suitable for
the Phase 1 hypothesis test.

---

### Transport gravity-axis pairing: straight
`(gh, gw, gd) = (gravity_x, gravity_y, gravity_z)`, matching the FFT's array-dimension order
(dim0→x, dim1→y, dim2→z). The swapped pairing produced diagonal-stripe / stacked-sheet artifacts in
every field — the transverse-flow signature of a rotated mapping. The *diagonal* (rather than
axis-aligned) artifact was the tell that it was an x↔y swap in the row–col plane, not a single-axis flip.

### Curvature: reverted to the random seed, not gravity-sourced
Curvature is left at its `seed_initial_curvature` value (`rng 0.0..0.1`) and is no longer overwritten
in the loop. Gravity-sourcing it (`curvature = gravity_curvature_coupling · |g|`) drove curvature to
~1e-14 — twelve-plus orders below the 0.08 threshold — so nothing could collapse. It also coupled
curvature to `transport_rate` (curvature ∝ gravity ∝ concentration ∝ transport_rate), making the two
knobs non-independent and the threshold impossible to calibrate stably. The random seed is
transport-independent: ~20% of cells exceed 0.08, and the dense knots among them collapse.

- **Trap to remember:** when reverting, remove *only* the curvature line from the gravity write-back
  loop. Commenting out the whole block also kills the `gravity_x/y/z` assignments, which zeroes
  transport and accretion (cell.gravity stays 0 → transport's `l1 <= 0` guard fires for every cell →
  smooth, unclumped matter).

### Accretion removed
The in-place `accretion` growth term is gone; transport is its conservative replacement. The non-BH
branch now only drains: `matter_density -= rip_drain_rate · rip_strength · matter_density`. Clean
split: **drain removes matter from the universe, transport redistributes what remains.**

### rip_drain_rate lowered to 1.25e-8
The diffuse drain is a strong, uniform, **one-way** matter sink. At 1.25e-6 it removed essentially
all matter over a run and single-handedly set a(t), masking the black-hole channel — the only channel
that has a reversal (contraction) mechanism. Lowering it ~100× demotes the leak to a slow background
drift (~6%/run) and lets formation/reversal drive a(t). This is the change that made contraction
visible. It also preserves matter so more of it clusters and collapses instead of leaking away.

### transport_rate = 0.025
0.05 rammed matter into a few super-dense spikes; 0.025 gives a graded web. Because transport only
flows downhill (no back-pressure), the rate sets the *timescale* of concentration, not the endpoint —
pick the rate that catches the transient web you want at the run length you use.

### Strategic: not fitting a constant Λ
Stopped trying to match late-time expansion to a cosmological constant. DESI (2025) reports mounting
hints that dark energy may be *evolving / weakening* rather than constant, so fitting ΛCDM's constant
Λ is fitting a target the data no longer clearly endorses. A matter-depletion mechanism is inherently
dynamical and naturally produces a weakening late-time driver; if/when expansion is revisited, the
target is the evolving w(z), not a constant. **Branch closed here; pivoting to supermassive black holes.**

---

## → ideas-to-explore.md

- **Cyclic / bouncing cosmology branch.** The phase2 contraction (a(t) bending negative on a reversal
  wave) is a proof-of-concept seed. As a cyclic model it carries a much more permissive observational
  bar than ΛCDM-matching. Parked, not abandoned.

- **Re-synchronizing driver for sustained cycles.** The single-pulse-then-settle behavior is a
  *de-phasing* problem, not a fuel problem (matter wasn't exhausted — density hit ~430). Sustained
  cycling needs something that re-triggers collapse in concert: the stochastic parent-BH feed (an
  episodic source that dumps matter and re-spikes the threshold across a region at once) is the
  candidate. Structural addition, not a parameter.

- **SMBH branch target (next).** Match the JWST overmassive-early-black-hole anomaly: BH-to-stellar
  mass ratio ~0.1–0.5% locally vs 10–30% at high redshift, with 10^6–10^8 M_sun holes already present
  at z≈8–10. Our edge: holes form by *instantaneous threshold crossing* (no slow-accretion time
  bottleneck), and parent-feed dumps can spike a cell into the `is_supermassive` tier. Falsifiable
  question: does the mechanism produce an early-heavy, high-ratio mass function, and does the
  supermassive tier *emerge* rather than being hand-set?

---

## Run settings — the reproducing recipe

> Verify column/table names first, then adjust the queries if they differ.
> Replace `run_id = 1` with the run you care about.
>

```sql
SELECT key, value
FROM run_setting
WHERE run_id = 1
ORDER BY key;
```
```
(paste result here)
```

### Timeseries — the arc (downsampled every 25 steps)
```sql
SELECT timestep, black_hole_count, total_matter, scale_factor_avg
FROM timestep_summary
WHERE run_id = 1 AND timestep % 25 = 0
ORDER BY timestep;
```
```
(paste result here)
```

### Contraction events — the headline evidence
Every step where a(t) decreased, with the black-hole count and total matter at that step.
Expectation: at these steps `black_hole_count` is falling (holes reverting) and `total_matter`
is rising (matter re-injected) — reversal driving the contraction.
```sql
SELECT a.timestep,
       a.black_hole_count,
       a.total_matter,
       a.scale_factor,
       a.scale_factor - p.scale_factor AS delta_a
FROM timestep_summary a
JOIN timestep_summary p
  ON p.run_id = a.run_id AND p.timestep = a.timestep - 1
WHERE a.run_id = 1
  AND a.scale_factor < p.scale_factor
ORDER BY a.timestep;
```
```
(paste result here)
```
_(For just the deepest contractions, swap the final line for `ORDER BY delta_a ASC LIMIT 20;`)_

### Key numbers
```sql
SELECT
  (SELECT MAX(black_hole_count) FROM timestep_summary WHERE run_id=1)                            AS peak_bh,
  (SELECT timestep    FROM timestep_summary WHERE run_id=1 ORDER BY black_hole_count DESC LIMIT 1) AS peak_bh_step,
  (SELECT total_matter FROM timestep_summary WHERE run_id=1 ORDER BY timestep ASC  LIMIT 1)        AS matter_first,
  (SELECT total_matter FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)        AS matter_last,
  (SELECT black_hole_count FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)    AS bh_last,
  (SELECT scale_factor FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)    AS a_last;
```
```
(paste result here)
```
---

## SMBH matter accounting: which side of the rip is the cell on? (smbh-phase1)

**Context.** To make SMBHs persist rather than drain and revert like normal black holes, we
need an inflow term — the SMBH should feed faster than it drains. The naive implementation
(`cell.matter_density += rate * density`) creates matter from nothing, which violates the
matter budget that drives the scale factor. Before treating that as a mere "known limitation,"
we asked whether the non-conservation is actually physical within the rip framework.

**The fork.** A black hole in this model is a threshold into a child geometry. Matter crossing
in leaves our spacetime (this is the basis for matter-loss-drives-expansion). The question is
what an SMBH *cell* represents for accounting purposes:

- **Parent-side feeder:** the SMBH is a sink in our universe; matter falling in leaves for the
  child. Under this reading the cell should *lose* matter, and persistence must come from
  conservative inflow from our own universe's neighbors (transport), not creation.
- **Child-side boundary:** the cell is where a *parent* universe's rip deposits matter into ours.
  Under this reading `+= matter` is correct — the matter is arriving from the parent through the
  boundary. It only looks non-conservative because the simulation models a single layer of what
  is, in the hypothesis, an infinite nested stack of geometries.

**Working position (not yet resolved).** The SMBH is plausibly *two-sided*: it exists in our
universe (mass, lensing) while its interior is the boundary to the child. The connection may run
both ways, so our SMBH is simultaneously our sink and our parent's drain. The apparent
non-conservation is then a bookkeeping artifact of modeling one layer, not a physics violation.

**Decision for this branch.** Implement persistence via the inflow term and treat the matter as
arriving from the parent geometry (child-side source), tagged conceptually as rip-return inflow.
This is flagged as non-conservative *within our single modeled geometry* in RESULTS.md, but the
reasoning above means it is not necessarily non-physical within the full framework. Revisit if/when
a multi-layer accounting is attempted. The conservative-transport alternative (feed the SMBH only
from its own neighbors) is recorded as the rejected-for-now option.
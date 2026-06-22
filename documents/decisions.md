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

## Galaxy Structure & SMBH Competition (galaxies branch)

### One dominant SMBH per galaxy emerges from competition, not enforcement
**Decision:** A galaxy has a single SMBH mass budget — a fraction of its baryonic
mass (total non-SMBH matter inside the galaxy radius). That budget is split among
all SMBHs in the galaxy in proportion to each one's `smbh_connection_strength`
relative to the galaxy's total connection strength. SMBHs are not capped
individually; they compete for one shared budget.

**Reason:** Capping each SMBH independently at a fraction of galaxy mass let N SMBHs
each grow to the cap, so total SMBH mass scaled with N — hundreds of overmassive
holes per galaxy. The fix had to make dominance *emerge* rather than be imposed.
A shared budget split by connection strength does this: because the connection
strength distribution is heavy-tailed, one SMBH per galaxy typically holds the
overwhelming majority of the budget and the rest are starved. We never write a
"one SMBH per galaxy" rule — the single dominant hole falls out of the competition.

**Why not enforce one-per-galaxy directly:** Special-casing the count in code is a
red flag — it would produce the right number for the wrong reason and hide whatever
the physics actually does. The same principle recorded for emergent inflation applies:
a result that emerges from a uniform rule is higher-quality evidence than one
engineered to appear.

**Cap is on baryonic mass, not total or stellar mass:** Using total galaxy mass made
the cap self-referential (a massive SMBH inflated total mass, raising its own cap —
runaway). Using stellar mass alone failed at early times when no stars had formed yet,
so the cap was zero and did nothing. Baryonic mass (total minus SMBH mass) is the
M-bulge reservoir: the matter available to feed the hole, independent of the hole's
own mass. This is the physically motivated denominator and the one that is non-zero
from the first timestep.

---

### The SMBH competition cap denominator must exclude SMBH mass — double-subtraction caused runaway (galaxy-phase2)
**Finding:** The competitive SMBH cap computes a per-galaxy baryonic budget, then
splits it by connection-strength share. The budget was being computed as
`total_mass[i] - smbh_mass[i]`. But `find_galaxies` already accumulates `total_mass`
from non-BH cells only — SMBH mass is tracked separately in `smbh_mass` and never
added to `total_mass`. So subtracting `smbh_mass` was a *second* subtraction of a
quantity that was never in the sum.

**Why it ran away:** As an SMBH grew, `smbh_mass[i]` grew, so the denominator
`total_mass[i] - smbh_mass[i]` shrank toward zero. Once `smbh_mass >= total_mass`,
the budget clamped to zero and hit the `baryonic_mass <= 0.0 { continue }` guard —
which *skips the cap entirely*. The result was a self-reinforcing loop: the bigger
an in-galaxy SMBH got, the more it suppressed its own budget, the more completely
it escaped the cap. The largest SMBHs were precisely the uncapped ones. In-galaxy
max mass climbed 10^10 → 10^11 → 10^16 and drove `gravity_magnitude_avg` to ~10^28.

**Fix:** `let baryonic_mass = total_mass[i].max(0.0);` — `total_mass` is already the
baryonic budget. One line.

**Consequence:** After the fix, in-galaxy max SMBH mass stays bounded (~10^1–10^2,
with transient excursions to 10^3–10^6 in newly-formed or just-merged galaxies that
relax back). `gravity_magnitude_avg` returned to sane values; the inflation
expansion-rate curve became clean. The SMBH mass function lost its 10^16 tail and
now tops out near 10^5–10^6 — still heavy-tailed (consistent with the JWST
overmassive regime) but no longer unbounded.

**Principle reinforced:** This is the third instance of the same bug class — a
quantity whose growth weakens its own constraint (cf. the rip drain rate, the
phantom `apply_gravity_interaction` additive feedback). The cap denominator must be
*independent of the thing being capped*. Guard against any cap whose budget shrinks
as the capped quantity grows.

---

### Emergent one-SMBH-per-galaxy via mass-dominance merge — threshold must beat the cap's mass-bunching (galaxy-phase2)
**Goal:** Drive the in-galaxy SMBH population toward ~1 dominant per galaxy (the
observed regime: ≈1, with rare transient post-merger duals), *emergently* from the
competition dynamics rather than an enforced "delete all but one" rule.

**Mechanism chosen.** The intra-galaxy merge (Pass 4 of `apply_smbh_competition`)
selects a winner — the most massive SMBH in the galaxy region — and absorbs any
non-winner whose mass falls below `galaxy_smbh_dominance_threshold × winner_mass`,
conserving mass into the winner. Winner-selection and absorption now key off the
SAME quantity (mass). The prior criterion absorbed on *connection-strength share*
while selecting the winner by mass — two different quantities — so comparable-
strength SMBHs all survived and galaxies kept hundreds.

**The cap/merge interaction — why the threshold value matters.** Pass 3 (the cap)
clamps every in-galaxy SMBH toward `baryonic_budget × share`, which *bunches* their
masses together. Pass 4 then only absorbs SMBHs far below the winner. These work
against each other: the cap makes everyone similar, so a low dominance threshold
finds nothing to absorb. Measured directly:
  - threshold 0.1 → avg SMBH/galaxy plateaued at ~2.4 (max 8). The cap bunches
    masses within ~10×, so "under 10% of the max" almost never triggers.
  - threshold 0.5 → avg SMBH/galaxy ≈1.0 across the whole run (max 2–3 early,
    1 late). Absorbing anything under half the dominant mass beats the cap's
    bunching and leaves a single winner plus rare near-equal duals.

**Decision:** Use `GALAXY_SMBH_DOMINANCE_THRESHOLD = 0.5`. The threshold is not a
free knob — it must exceed the mass spread the cap imposes, or the merge is inert.
This is the emergent route: one-per-galaxy falls out of (FoF region) + (mass-keyed
gradual merge), no special-casing. Transient duals (max 2–3) survive a few steps
when two comparable SMBHs share a just-merged region, matching the real post-merger
pre-coalescence regime.

**Why not exempt the dominant SMBH from the cap (the considered alternative):** that
would also break the bunching, but reintroduces runaway risk on the dominant one.
The threshold bump achieved the goal without touching the cap, so the cap's runaway
protection stays fully intact. Rejected-for-now, recorded here.

**Gate condition for revisiting:** If a future change to the cap (e.g. raising
`galaxy_smbh_mass_fraction_cap`) widens the in-galaxy mass spread, the 0.5 threshold
may stop reaching the bunched losers and avg SMBH/galaxy will climb above ~1.5 —
re-tune the dominance threshold upward, or revisit the cap-exemption alternative.
The old `galaxy_smbh_stall_share_threshold` setting is retained but unused; remove
it if the connection-share criterion is not revived.

---

### Orphan SMBHs are self-limiting, not a runaway — treated as an emergent feature (galaxy-phase2)
**Finding:** Because SMBH formation is exogenous (decoupled from galaxies), ~95% of
SMBHs form outside any FoF galaxy (`galaxy_id == 0`) and are structurally invisible
to the competition cap, which only acts on in-galaxy SMBHs. A diagnostic instrument
measured the in-galaxy/orphan split and the max mass of each population per 100
timesteps over a full 5000-step run.

**What the data showed:** Orphan max mass climbs to ~10^6 by t≈1600, then *wanders
around a few ×10^6 for the remaining 3400 timesteps* (1e6, 2e6, 3.9e6, 7e5, 3.4e6 —
fluctuating, not climbing). This is bounded equilibrium, not geometric runaway. A
true runaway adds orders of magnitude per decade of time (cf. the in-galaxy bug
above: 10^10 → 10^16). Orphans do not.

**Interpretation:** Orphan growth self-limits because it is tied to local conditions
(`SMBH_CONNECTION_MODE = tied_to_curvature`). An orphan sits in a drained void with
low local curvature, so its growth rate falls as its surroundings thin. The cap
(for in-galaxy SMBHs) and local-curvature coupling (for orphans) are two distinct
bounding mechanisms — both bounded, at different ceilings. The in-galaxy ceiling is
low (a fraction of host baryonic budget); the orphan ceiling is higher (~10^6) but
stable.

**Decision:** No orphan-specific brake is added. The rising orphan fraction over
time — as galaxies merge away (count 312 → ~12) and their SMBHs are widowed — is
read as a *prediction* of the matter-loss framework: SMBHs increasingly dominate
over thinning baryonic surroundings as structure dissolves at late times. Adding an
explicit orphan cap would be engineering an answer where the existing uniform rules
already produce a bounded one.

**Gate condition for revisiting:** If a 10000-step run shows `max_orphan_mass`
climbing past ~10^7 rather than holding near 10^6, the self-limiting read is wrong
and orphan growth has an unbounded source (e.g. connection strength frozen at
formation rather than recomputed against current local curvature). Check whether
`smbh_connection_strength` updates over time before adding any brake.

---

### Stalled SMBHs merge into the galaxy's dominant hole
**Decision:** An SMBH whose competitive share falls below
`galaxy_smbh_stall_share_threshold` is merged into its galaxy's most massive SMBH.
Its mass transfers to the winner; the stalled cell reverts to ordinary matter
(`is_black_hole` and `is_supermassive` cleared, connection strength zeroed).

**Reason:** In reality every black hole in a galaxy spirals to the center via
dynamical friction and merges — there is no stable configuration of hundreds of
co-orbiting SMBHs. Simulating the full inspiral is unnecessary; the end state is
known. The share threshold is our knob for *when* we declare the merge has happened
rather than tracking the orbit. This also makes `smbh_count` report real surviving
holes instead of counting starved seeds that carry no mass.

**Mass is conserved in the merge:** the loser's matter is added to the winner's cell,
not discarded. The galaxy's SMBH budget is unchanged by a merge — only its
distribution across cells changes (consolidating toward the winner).

**Math-driven, sweep-tunable:** the threshold is a single `app_setting`, so the
parameter sweep tool can locate the value at which the surviving-SMBH count matches
the observed one-per-galaxy expectation, rather than that count being hardcoded.

---

### Star formation gated on matter stability (post-inflation only)
**Decision:** A cell may only become a star when the previous timestep's
`|matter_delta|` is below `star_formation_max_matter_delta`. `previous_matter_delta`
is initialized to infinity so formation is blocked until the first real delta proves
the universe has stabilized.

**Reason:** Stars cannot form while spacetime is expanding too rapidly for matter to
gravitationally collapse — the analog of the pre-recombination epoch, when the
universe was too hot for neutral structure. `matter_delta` is already the quantity
that drives the scale factor, so its magnitude is a natural in-simulation proxy for
"how violent is the current epoch" without introducing a separate clock or a magic
timestep number. Gating on it means star formation switches on by itself once the
inflation burst settles, rather than at a hardcoded time.

**The initialization matters:** seeding `previous_matter_delta` at 0.0 read as
"perfectly stable" on timestep 0 and let stars form during the most violent part of
the run. Infinity is the correct default — maximally unstable until proven otherwise.

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
key                                 value
ACCRETION_RATE	                    1e-6
BH_DRAIN_RATE                       0.01
BLOB_COUNT	                        5
BLOB_PEAK_DENSITY	                  10.0
BLOB_SIGMA_MAX	                    8.0
BLOB_SIGMA_MIN	                    2.0
COLLAPSE_DENSITY_THRESHOLD	        1.5
CURVATURE_THRESHOLD                 0.08
DARK_GRAVITY_BOOST                  1.0
DARK_MATTER_RATIO                   0.85
DECAY_DIFFUSION_COEFF               0.1
DECAY_FACTOR                        0.9999
DECAY_HEALING_BASE                  0.05
DECAY_HEALING_DAMPING               1.0
DECAY_INVERSE_RATE	                0.05
DECAY_MATTER_RATE                   0.05
DECAY_MATTER_THRESHOLD              0.001
DECAY_TIME_RATE                     0.05
GALAXY_CAPTURE_DENSITY_THRESHOLD    0.1
GALAXY_COUNT                        50
GALAXY_CURVATURE_BOOST              0.05
GALAXY_FORMATION_DENSITY_THRESHOLD  0.5
GALAXY_MASS_GROWTH_RATE	            1e-6
GALAXY_MERGE_OVERLAP_FRACTION       0.75
GALAXY_OVERDENSITY                  3.0
GALAXY_RADIUS                       4.0
GALAXY_SMBH_MASS_FRACTION_CAP       0.1
GRAVITY                             6.67430e-11
GRAVITY_CURVATURE_COUPLING          0.0025
GRAVITY_DENSITY_COUPLING            0.025
INF_GRID_DEPTH                      64
INF_GRID_HEIGHT                     64
INF_GRID_WIDTH                      64
INITIAL_GEOMETRY                    perlin
LIGHT_SPEED                         3.0e8
MATTER_EXPANSION_RATE               1e-6
MAX_SIMULATION_TIME                 10.0
NUM_CORES                           0
NUM_RUNS                            1
NUM_TIMESTEPS                       5000
PERLIN_AMPLITUDE                    1.0
PERLIN_FREQUENCY                    0.05
PERLIN_OCTAVES                      4
PERLIN_SEED                         42
QUIET                               0
RIP_CURVATURE_WEIGHT                0.5
RIP_DECAY_MECHANISM                 self_healing
RIP_DECAY_RATE                      0.05
RIP_DENSITY_WEIGHT                  1.0
RIP_DRAIN_RATE                      1.25e-8
RIP_EVAPORATION_RATE                0.05
RIP_INDUCED_THRESHOLD               50000
RIP_INITIAL                         1e4
RIP_MINIMUM_STRENGTH                1e-6
SMBH_ACCRETION_RATE                 0.03
SMBH_CONNECTION_ALPHA               4.0
SMBH_CONNECTION_CURVATURE_RATE      6.0
SMBH_CONNECTION_INDEPENDENT_RATE    0.03
SMBH_CONNECTION_MODE                tied_to_curvature
SMBH_CURVATURE_THRESHOLD            0.095
SMBH_EARLY_BIAS                     300.0
SMBH_FORMATION_PROBABILITY          0.02
SMBH_INITIAL_DENSITY                50.0
STAR_BURN_RATE                      0.0001
STAR_EXTINCTION_THRESHOLD           0.4
STAR_FORMATION_MAX_MATTER_DELTA     50.0
STAR_FORMATION_THRESHOLD            0.8
STRUCTURE_NUM_PARTICLES             1000
TIME_STEP_SIZE                      0.01
TRANSPORT_RATE                      0.025
UNIFORM_DENSITY                     1.0
```

### Timeseries — the arc (downsampled every 25 steps)
```sql
SELECT timestep as st, black_hole_count, total_matter, scale_factor
FROM timestep_summary
WHERE run_id = 1 AND timestep % 25 = 0
ORDER BY timestep;
```
```
st    black_hole_count  total_matter      scale_factor
0     11187             254876.750173958	1.02934751978424
25	  14417	            249323.566957022	1.03507957600435
50	  15973	            245957.297573483	1.0385698039184
75	  13759	            245828.357253629	1.0387037260749
100	  12330	            242899.6224866    1.04175027287623
125	  12371	            239744.492368874	1.04504232122679
150	  11279	            238064.607907908	1.0467993469702
175	  8531	            236883.336942392	1.04803663128564
200	  9405	            232492.027745765	1.05264900394833
225	  10337	            228919.81041496   1.05641601925634
250	  9944              226343.369941337	1.05914132152732
275	  10516	            222580.789777964	1.06313393220249
300	  13254	            217630.803965421	1.06840947624587
325	  14876	            213779.539243416	1.07253213760483
350	  15872	            210118.317287277	1.07646611299981
375	  16984	            206506.036655352	1.08036164232737
400	  17763	            203379.746260048	1.08374445162012
425	  18243	            200296.123527111	1.08709146846429
450	  18745	            197253.55142909   1.09040405947728
475	  19089	            194613.175390877	1.09328694049802
500	  19262	            191951.178738777	1.09620114375217
525	  19365	            189412.356976597	1.09898773890909
550	  19579	            186980.986897854	1.10166303581488
575	  19655	            184560.837109833	1.1043324542708
600	  19693	            182263.976160351	1.10687186758349
625   19764             180077.901126049	1.10929421929601
650	  19710	            177981.961174192	1.11162167161671
675 	19710	            175820.685375536	1.11402679075952
700	  19752	            173759.365976334	1.1163255241925
725	  19638	            171898.470341231	1.11840482356735
750	  19570	            169893.439956131	1.1206495088005
775	  19582	            167973.894924655	1.12280271192117
800	  19485	            166275.789692523	1.12471096883291
825	  19489	            164343.823083889	1.12688597321045
850	  19416	            162595.212133658	1.12885818217344
875	  19396	            160909.350365551	1.13076288610703
900	  19294	            159234.227988595	1.13265863968691
925	  19223	            157652.833433386	1.1344512369208
950	  19192	            156036.860429997	1.13628596152678
975	  19132	            154443.057063584	1.13809842188651
1000	19056	            152937.288851364	1.13981342518725
1025	18965	            151495.249790703	1.1414582663458
1050	18897	            150051.558244927	1.14310737010693
1075	18866           	148593.714419263	1.144775057447
1100	18802           	147214.057620921	1.14635554415149
1125	18742	            145837.980316357	1.14793410385976
1150	18697	            144502.026549725	1.14946871560658
1175	18652	            143155.268412454	1.15101781484973
1200	18598	            141905.312481888	1.15245743593761
1225	18525	            140665.746756359	1.15388686843006
1250	18443	            139461.618194277	1.15527713342666
1275	18426	            138221.634135425	1.1567105471771
1300	18326	            137104.072830827	1.15800396472733
1325	18284	            135969.421300623	1.1593186414068
1350	18222	            134827.35361686   1.16064341811067
1375	18211	            133687.61261706   1.16196700513036
1400	18201	            132542.936854369	1.1632978421413
1425	18130	            131496.288148618	1.16451604372553
1450	18064	            130461.556856683	1.16572162853653
1475	18015	            129464.247089765	1.16688479402392
1500	18008	            128411.423378262	1.16811396494026
1525	17928	            127456.583869953	1.16922985896927
1550	17872	            126512.519019032	1.17033420898876
1575	17847	            125535.322801821	1.17147841411607
1600	17780	            124624.735377435	1.17254563345241
1625	17763	            123693.607620793	1.17363793169334
1650	17740	            122735.113818142	1.17476339566638
1675	17710	            121851.121689103	1.17580233640169
1700	17674	            120980.436456421	1.17682653594555
1725	17627	            120132.222454086	1.17782516015531
1750	17603	            119289.956220439	1.17881762041606
1775	17546	            118454.545922064	1.17980282826515
1800	17521	            117649.239557029	1.18075331365684
1825	17467	            116869.53038169   1.18167431685997
1850	17471	            116053.654302351	1.18263881006864
1875	17412	            115330.053205305	1.18349487849768
1900	17385	            114552.455679654	1.18441551908436
1925	17369	            113778.709555226	1.18533231063818
1950	17337	            113096.156271963	1.1861416392721
1975	17313	            112289.471381868	1.18709886784902
2000	17273	            111583.514623956	1.18793720419687
2025	17261	            110850.690278741	1.18880807255849
2050	17227	            110191.447062156	1.18959204460188
2075	17213	            109505.443846873	1.19040838854462
2100	17182	            108865.040714341	1.19117097396062
2125	17164	            108199.382184852	1.19196415104277
2150	17128	            107523.67746644   1.19276983901674
2175	17126	            106867.031188575	1.19355332410001
2200	17088	            106244.538927161	1.19429653310478
2225	17077	            105594.415925271	1.19507322519737
2250	17051	            104985.814776922	1.19580076950428
2275	17030	            104381.270590074	1.196523902469
2300	17013	            103787.713632661	1.19723431837131
2325	17000           	103186.76262013   1.19795401377636
2350	16988	            102584.916679249	1.19867521454102
2375	16971	            102006.225325126	1.19936907827118
2400	16958	            101427.458827433	1.20006343382754
2425	16956	            100836.754571924	1.20077252581599
2450	16926	            100298.222749736	1.20141935418555
2475	16909            	99755.5035585738	1.20207156449321
2500	16907            	99192.8654229987	1.20274808609767
2525	16896            	98655.418294952   1.20339467333997
2550	16887            	98097.4766452995	1.20406628469174
2575	16868            	97566.4123566103	1.20470589111779
2600	16858            	97072.1528330756	1.20530147565208
2625	16853            	96536.6510828473	1.2059470895501
2650	16858            	95992.3009202733	1.20660372574815
2675	16845            	95467.9718243821	1.20723654907811
2700	16820            	94964.7839866056	1.2078441686875
2725	16793            	94487.7066280124	1.20842054126932
2750	16801            	93980.8507047699	1.20903319162804
2775	16789            	93509.1764426578	1.20960359597852
2800	16791            	93015.1216141407	1.2102013541262
2825	16778            	92537.4561768223	1.2107795635696
2850	16768            	92061.5690483266	1.21135589510285
2875	16768            	91590.5833743878	1.21192656075261
2900	16753            	91131.3681070812	1.21248322373645
2925	16748            	90672.4377084654	1.21303979685003
2950	16752            	90183.3108294872	1.21363327235051
2975	16733            	89735.76351802	  1.21417655222131
3000	16728            	89280.444008276	  1.21472951637194
3025	16714            	88852.8693757167	1.21524901495286
3050	16724            	88358.2517943032	1.2158502471592
3075	16715            	87941.5334686144	1.21635701982188
3100	16701            	87502.5893051532	1.21689104983252
3125	16693            	87063.1626400143	1.21742590171387
3150	16693            	86647.0771247553	1.21793256039683
3175	16685            	86231.3301764405	1.21843901741376
3200	16674            	85818.5826131649	1.21894202895044
3225	16675            	85387.7888850745	1.21946725465527
3250	16665            	84958.3819144737	1.21999101483993
3275	16663            	84540.2618210884	1.22050122425395
3300	16663            	84122.3865457702	1.22101134811571
3325	16653            	83730.9561269582	1.22148938265161
3350	16646            	83333.0326381602	1.22197553868832
3375	16653            	82916.8942091602	1.22248415548942
3400	16633            	82532.2086046285	1.22295451801085
3425	16635            	82130.4315378522	1.22344597181072
3450	16628            	81736.6513879585	1.22392783541682
3475	16632            	81345.196880411	  1.22440704127244
3500	16622            	80956.8606544952	1.22488261521715
3525	16613            	80583.4089250125	1.22534013517371
3550	16613             80189.8980658904	1.22582241470791
3575	16612             79819.1934829525	1.22627691693273
3600	16602             79446.6565818834	1.22673383543944
3625	16592             79088.9928001987	1.22717267217547
3650	16589             78736.1831392169	1.22760570693483
3675	16589             78364.0554479079	1.22806261802175
3700	16589             78001.5029664355	1.22850793589199
3725	16583             77608.1112562635	1.22899131580244
3750	16578             77256.9331673483	1.22942298641621
3775	16571             76914.8946091207	1.22984356840547
3800	16574             76566.141043321	  1.23027255553637
3825	16567             76221.8673878183	1.23069617888333
3850	16569             75864.7464802333	1.23113576470767
3875	16569             75507.5540437524	1.23157559563856
3900	16560             75170.1816482745	1.23199116534441
3925	16557             74824.2628054085	1.23241740802118
3950	16553             74488.9483264192	1.23283072471391
3975	16545             74160.129884749	  1.23323616884676
4000	16543             73827.4653806513	1.23364649099132
4025	16540             73497.3481022922	1.23405380624059
4050	16547             73166.1486912294	1.23446259182547
4075	16540             72821.3695521539	1.23488828215546
4100	16547             72489.5112563164	1.23529815808293
4125	16531             72175.6436341471	1.23568593903123
4150	16536             71842.6669364168	1.23609746216465
4175	16532             71524.5414407421	1.23649075883803
4200	16530             71192.8605508156	1.23690094721537
4225	16528             70875.3669971951	1.23729371764032
4250	16526             70559.2461484252	1.23768491380989
4275	16527             70248.5290854519	1.23806954338359
4300	16526             69928.3799403668	1.2384659737445
4325	16529             69619.9668745839	1.23884799173897
4350	16519             69324.6264482164	1.23921392766823
4375	16515             69010.0458904674	1.23960382160008
4400	16517             68682.9422388009	1.24000936686079
4425	16519             68379.4163283519	1.24038579895839
4450	16517             68075.0155740242	1.24076343080405
4475	16511             67771.3806058016	1.24114022717031
4500	16515             67466.9505524896	1.24151812507466
4525	16510             67169.6672982993	1.24188726248949
4550	16512             66867.1951814011	1.2422629555742
4575	16513             66568.8638405139	1.24263361683465
4600	16510             66294.3224337266	1.24297481805073
4625	16506             66002.3677363427	1.2433377633668
4650	16498             65721.5986419739	1.24368690319616
4675	16505             65418.5654367644	1.24406383873382
4700	16502             65129.1432487209	1.24442395052175
4725	16495             64837.3045091885	1.24478717463777
4750	16492             64569.0946368629	1.2451210836238
4775	16493             64278.2522048561	1.24548327033498
4800	16502             63987.1164345227	1.24584592785505
4825	16490             63714.4304579328	1.24618569889186
4850	16489             63432.0501226029	1.24653764691666
4875	16485             63160.2285979002	1.24687652873604
4900	16484             62882.7269660525	1.24722258702113
4925	16486             62608.0878938585	1.24756517011645
4950	16486             62327.2843928358	1.24791553997421
4975	16484             62068.1677503133	1.24823893755611

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
timestep  black_hole_count  total_matter      scale_factor      delta_a
69	      16305	            244339.782644656	1.04025106544711	-0.000195615067465571
70	      15872	            244595.044558141	1.03998556285743	-0.000265502589679611
71	      15406	            244875.649309118	1.03969377890744	-0.000291783949989854
72	      15005	            245107.663237322	1.0394525834511	  -0.000241195456338161
73	      14571	            245363.261918196	1.03918693469312	-0.00026564875797952
74	      14131	            245622.714404359	1.03891735003305	-0.000269584660076205
75	      13759	            245828.357253629	1.0387037260749	  -0.000213623958144282
76	      13412	            246010.544074098	1.03851450518294	-0.000189220891962716
77	      13104	            246152.735141332	1.03836684819511	-0.000147656987828926
78	      12815	            246281.098530751	1.03823356846132	-0.000133279733792513
79	      12575	            246352.254516828	1.03815969455629	-7.38739050261117e-05
80	      12399	            246359.006316145	1.03815268513404	-7.00942225306811e-06
81	      12193	            246379.550735723	1.03813135710878	-2.13280252632231e-05
154	      10804	            238013.549937194	1.04685279578508	-4.13986141567513e-06
155	      10656	            238020.187774503	1.0468458469696	  -6.94881548279902e-06
156	      10496	            238026.184149418	1.04683956970824	-6.2772613556028e-06
157	      10339	            238032.912719351	1.04683252599869	-7.04370955650901e-06
160	      9927	            237968.453100134	1.04690000659956	-1.18590026341181e-05
162	      9629	            237937.964890694	1.04693192519279	-1.55024632952916e-06
```
_(For just the deepest contractions, swap the final line for `ORDER BY delta_a ASC LIMIT 20;`)_

### Key numbers
```sql
SELECT
  (SELECT MAX(black_hole_count) FROM timestep_summary WHERE run_id=1)                              AS peak_bh,
  (SELECT timestep    FROM timestep_summary WHERE run_id=1 ORDER BY black_hole_count DESC LIMIT 1) AS peak_bh_step,
  (SELECT total_matter FROM timestep_summary WHERE run_id=1 ORDER BY timestep ASC  LIMIT 1)        AS matter_first,
  (SELECT total_matter FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)        AS matter_last,
  (SELECT black_hole_count FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)    AS bh_last,
  (SELECT scale_factor FROM timestep_summary WHERE run_id=1 ORDER BY timestep DESC LIMIT 1)        AS a_last;
```
```
peak_bh peak_bh_step matter_first     matter_last       bh_last   a_last
19792   628	         254876.750173958 61822.6611639176	16478     1.24854542605761
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
---

## Dark matter that clusters and lenses: dimple movement (darkmatter-phase1, Tier 0 + 1)

**Context.** The 5000-step run validated two things about the static fossil dimple — it stays
bounded under expansion dilution (total plateaus ~15.6k, max ~7) and inflation survives with the
early contraction now understood as a one-off black-hole-reversion ringdown, not a recurring
oscillation. But the `rip_dimple` projection (cmb_rip_dimple) showed the field is a near-uniform,
space-filling fog with mild texture — the *opposite* of the sharply-clumped matter field. This
fails the original motivation in two ways. A nearly-uniform mass distribution (a) does not bind
galaxies differentially — by symmetry a uniform component exerts no net internal force — and
(b) produces no lensing signal, because convergence/shear require density *contrast*, not mere
presence. The deposit-everywhere + uniform-dilution + pinned-to-cell design guarantees the fog:
it records where rips have *ever* happened (≈ everywhere over a long run) rather than where
structure *is now*. A fossil records the past; a halo has to track the present.

**The realization.** Both canonical cold-dark-matter signatures — flat rotation curves / holding
galaxies together, and gravitational lensing offset from the baryons (the Bullet Cluster) — come
from the same missing ingredient: the dimple must *cluster*, producing density contrast that is
spatially distinct from the baryonic matter. "Lensing where there is no matter" is not exotic; it
is the defining dark-matter observable, and it falls out for free once a gravitating dimple
concentrates somewhere the baryons are sparse.

**The fork, and why we take the cheap branch first.**
- *Tier 1 — overdamped advection (taken now):* move `rip_dimple` down the total gravity gradient
  with a conservative two-pass scheme mirroring `apply_matter_transport`, collisionless (every cell
  participates, flux crosses black-hole cells freely). This clusters the dimple into wells and
  drains voids, creating the contrast lensing needs, and — being conservative — leaves the
  boundedness argument intact (dilution stays the only sink). It yields *halos* but NOT the
  Bullet-Cluster pass-through offset, because an overdamped single-velocity grid field settles into
  wells and cannot multi-stream.
- *Tier 2 — collisionless particles (deferred):* the spatial offset in a head-on collision requires
  two streams occupying the same place with different velocities. A grid field (even one carrying
  momentum) averages to one velocity at the collision point and merges the streams. True
  pass-through needs a particle/particle-mesh representation (the existing `particle.rs` /
  `structure_particle.rs` scaffolding is the natural substrate). This is the larger architectural
  move and is not attempted until Tier 1 is validated.

**Tier 0 — measure before tuning.** Before judging Tier 1 we wired a lensing diagnostic on the
existing (previously unused) `cell.is_lensing_candidate` field: a cell is flagged when
`rip_dimple > LENSING_DIMPLE_MIN` and `matter_density < LENSING_MATTER_MAX` (gravitating dark
matter where baryons are sparse). `plot_lensing.py` projects dimple and baryon surface density,
reports `r(dimple, baryon)` (≈0 for the fog, rising toward positive as the dimple co-locates) and
the centroid offset, and maps the candidate cells. Run on the static-fossil field this gives the
baseline co-location so the effect of switching transport on is measurable, one variable at a time.

**Decision.** Implement Tier 0 + Tier 1 on this branch. New settings: `DIMPLE_TRANSPORT_RATE`
(0.025, at parity with baryon `TRANSPORT_RATE`; **0 disables and recovers the static fossil** —
the change is a clean reversible toggle), `LENSING_DIMPLE_MIN` / `LENSING_MATTER_MAX` (0.5 / 0.5,
tunable diagnostic thresholds calibrated after seeing the first distributions).

**Conceptual cost, recorded explicitly.** Turning on `apply_dimple_transport` is the line where the
dimple stops being the "pure static geometric fossil decoupled from mass" of the original
darkmatter-phase1 decision and becomes a *mobile substance*. That earlier framing is hereby
narrowed: the dimple is still mass-decoupled at the deposit (the GR break stands), but it is no
longer positionally frozen. This is the cost of the CDM branch and is accepted provisionally.

**Gate condition for Tier 2.** Do not start the particle work until Tier 1 is validated, namely:
(1) `total_dimple` remains bounded with transport on (conservation + dilution should preserve the
plateau); (2) the dimple develops genuine contrast and *co-locates* with structure — `r(dimple,
baryon)` climbs from ~0 toward positive and lensing candidates concentrate on/around galaxies
rather than filling voids; (3) local `max_dimple` stays manageable (clustering will raise it well
past the ~7 fog value; watch for stiff gravity feedback or a broken dilution bound). If clustering
either fails to emerge or runs away, fix Tier 1 (or reconsider the dark-energy reframing) before
spending effort on the collision offset.
# Ideas to Explore

A running list of hypotheses and directions to investigate once the core simulation is working. Not active work — parked for later.

---

## Rips and the matter/antimatter asymmetry

**Hypothesis:** Rips and antimatter interact like opposite magnetic poles — intrinsic attraction as a built-in property of how rips work, not a separate mechanism that needs its own explanation. Matter behaves as the "like pole" and isn't attracted the same way.

**Why it's interesting:** If the simulation produces this behavior, it could offer an explanation for the early-universe antimatter problem. Rather than antimatter being annihilated away, it would be sequestered/trapped by rips as a natural consequence of how they work.

**Things to think through when revisiting:**
- What in the rip geometry or dynamics produces the polarity? (Needs to be specific enough to make predictions.)
- How does this interact with CPT symmetry, which is the usual hurdle for baryogenesis explanations?
- Does the mechanism predict antimatter is still *somewhere* (trapped, sequestered, observable in principle) vs. removed entirely?
- Observational signatures that could distinguish this from other proposals (standard baryogenesis, leptogenesis, etc.)
- Does it need to happen only in the early universe, or would rips still be attracting antimatter today? If today, what would we expect to see?

---

## Universe-inside-a-black-hole

**Hypothesis:** If the math pans out, the best explanation for what we observe is that our universe exists inside a black hole.

**Why it's interesting:** Would naturally account for several features that otherwise need separate explanations — the apparent boundary/horizon structure, the one-way flow of time, why the universe looks the way it does from the inside. It also connects to a growing line of cosmological thinking (Poplawski and others) that takes this seriously rather than as metaphor.

**Things to think through when revisiting:**
- What in the simulation specifically points to this vs. other large-scale geometries?
- How does the parent black hole relate to the rips? Are rips a feature of the interior geometry?
- Testable predictions that distinguish this from standard ΛCDM cosmology.
- Relationship to the antimatter/rip hypothesis above — do they reinforce each other or are they independent claims?

---

## Holographic storage of lost information

**Hypothesis:** Information from matter lost to rips (or otherwise "removed" from the bulk) isn't destroyed — it's stored holographically as part of the geometry of the universe itself.

**Why it's interesting:** Directly addresses the black hole information paradox, but generalized: any information apparently lost to a rip is preserved on the boundary/geometric structure rather than destroyed. Fits naturally with the universe-inside-a-black-hole picture, since the holographic principle is already how information is thought to be preserved on black hole horizons.

**Connection to the Hawking information paradox:**
Hawking's original result was that black holes emit thermal (random) radiation as they evaporate, which would mean quantum information about infalling matter is permanently destroyed — a violation of unitarity. This became one of the deepest problems in theoretical physics. Hawking eventually moved toward preservation: his 2016 "soft hair" paper (with Perry and Strominger) proposed that infalling particles leave imprints on the horizon itself, encoding information in subtle gravitational and electromagnetic field configurations.

Rip sidesteps the paradox structurally rather than patching it. In standard GR, the black hole interior terminates at a singularity — there's nowhere for the information to go, so either it's destroyed (Hawking's original position) or it has to escape via the radiation (the holographic rescue). In Rip, the interior *is a functioning child geometry* where matter continues to evolve. Information isn't lost; it relocates across a geometric phase boundary. The paradox only exists if there's nowhere for the information to go. Rip gives it somewhere.

This also reframes what holographic imprinting means. In standard black hole physics, the horizon encodes information as a kind of emergency backup. In Rip, the rip boundary is a genuine interface between two real spaces — the imprinting isn't a rescue mechanism, it's a natural consequence of matter crossing a phase boundary where both sides are real.

**Things to think through when revisiting:**
- What's the boundary in this picture? The cosmological horizon? The parent black hole's horizon? The rips themselves?
- Does the simulation actually produce a holographic encoding, or is that an interpretation laid on top?
- How does information get *out* (or does it)? Is it accessible in principle, or only preserved in a formal sense?
- Connection to AdS/CFT and existing holographic frameworks — does this fit, extend, or conflict?
- If rips store information holographically, does that constrain what rips can do or where they can form?
- **Testable discriminator:** Does the parent-side cell retain any residual signature when matter crosses a rip threshold — a curvature imprint, a field perturbation, anything — or does it simply lose mass and nothing else? If there's a residual, that's a holographic imprint in the simulation itself. If there isn't, the information is genuinely transferred to the child geometry with no boundary record. Both are physically interesting but predict different things about what an observer near a rip boundary would measure.
- The "soft hair" result is suggestive: if horizon imprints are real in standard GR, the rip boundary should carry analogous structure. What would soft hair look like on a rip boundary in this model?

---

## Universal constants as a function of parent geometry

**Hypothesis:** The fundamental constants of a universe (gravitational constant, speed of light, dark matter ratio, etc.) aren't arbitrary — they're determined by the initial geometry of the matter distribution that formed the parent black hole. Different pre-collapse geometries in the parent universe produce different physics in the resulting child universe.

**Why it's interesting:** This provides a *mechanism* for the multiverse explanation of fine-tuning, rather than treating "many universes with random constants" as a brute postulate. The variation in constants becomes a consequence of the variation in pre-collapse matter arrangements — something the simulation can actually model and test, since its already parametrizing both initial geometry and physics constants. If certain geometry → constant relationships are stable across runs, that's a real, testable mapping.

It also ties together three threads already in play: the universe-inside-a-black-hole picture, the initial-geometry parameter sweep, and the per-universe rolled physics constants. Currently those are independent knobs in the simulation; this hypothesis says they're causally linked.

**Things to think through when revisiting:**
- Does the simulation show any stable correlation between initial geometry parameters and emergent large-scale behavior? (E.g., do Perlin-noise universes settle into different effective constants than Gaussian-blob universes?)
- What would be the "translation function" between parent geometry and child constants? Is it the total mass, the entropy, the angular momentum, the topology of the collapsing region?
- Does this make fine-tuning *less* mysterious or *more*? On one hand it grounds the multiverse explanation in a mechanism; on the other, it raises the question of why the parent universe's geometry distribution is what it is.
- Connection to the antimatter/rip hypothesis — if parent geometry sets rip behavior, and rip behavior affects matter/antimatter dynamics, then geometric variation predicts variation in baryogenesis efficiency across universes.
- Testable from inside our universe? Probably not directly, but indirect signatures might exist if our constants encode information about a specific parent geometry.
- Practical: this argues for the simulation eventually doing the inverse problem — given a target set of constants, what parent geometries produce them? Could narrow down what our parent black hole "looked like."

---

## Proper long-range gravity via Poisson solver

**Deferred work, not a hypothesis.** Currently `compute_gravity_from_density` only looks at immediate grid neighbors — gravity is treated as a local stencil rather than the long-range force it actually is. This is fine as a placeholder but means cells "feel" only their adjacent neighbors, which doesn't match how gravity works at any real scale.

**The fix:** Solve `∇²φ = 4πGρ` (Poisson's equation) for the gravitational potential across the grid, then take its gradient to get the gravity vector field. Standard approach in cosmological N-body sims. Done in Fourier space via FFT, it's `O(N³ log N)` per timestep, which is tractable on a 64³ grid. The `rustfft` crate handles the FFT part cleanly.

**Why it matters:**
- Captures all-pairs gravity, not just adjacent-cell pulls
- Eliminates artifacts at grid boundaries from the local-stencil approximation
- Makes the simulation actually comparable to standard cosmological codes
- May affect tuning of every other parameter, since current dynamics are running on a different physics

**When to revisit:** After current rip/decay/scale-factor dynamics are stable and producing sensible behavior. The current process needs to be a known baseline first, otherwise switching to proper gravity makes it impossible to tell whether new behavior comes from better physics or from some other tuning shift happening at the same time.

**Things to think through:**
- Boundary conditions: periodic (universe wraps around), zero-padded (universe sits in empty space), or something else? Each gives different behavior.
- Does the rip also need long-range treatment, or is it conceptually local? Probably depends on which decay mechanism is chosen.
- The `cell.gravity_x/y/z` storage stays the same; only the computation changes.
- Existing tuning (curvature_threshold, density thresholds, weights) will likely need recalibration after the switch.

---

## Cyclic universe with leaky boundaries

**Hypothesis:** The universe undergoes damped cycles driven by the rip field and black hole formation/healing. Each cycle is smaller than the last due to matter lost beyond gravitational reach during expansion.

**The cycle:**
1. Rip drives inflation, black holes form, matter drains into rips
2. Rip weakens, black holes slowly heal (self-healing decay mechanism), matter returns
3. Gravity dominates, returned matter recollapses, new black holes form
4. Repeat — but each cycle starts with less total matter than the last

**The leak:** Inertia is treated as intrinsic to matter (not emergent from Mach's principle). Matter carried beyond gravitational reach during inflation coasts forever and never returns. Each cycle is irreversible at the boundary.

**End state:** Eventually insufficient matter remains to trigger black hole formation, the rip field is never fed, expansion never restarts. Heat death reached cyclically rather than in one shot.

**Dependencies:** Requires black hole healing (return path for matter) to be implemented before this can be tested. See `RipDecayMechanism::SelfHealing`.

# Machian inertia

**Hypothesis:** Inertia is emergent from the gravitational relationship with all 
other matter in the universe rather than intrinsic to matter. As the universe 
expands and matter disperses, effective inertia weakens — distant matter slows 
naturally rather than coasting forever.

**Why it matters:** Would close the "leaky boundary" problem in the cyclic universe 
model — matter carried far by inflation would eventually return rather than being 
permanently lost.

**Why it's deferred:** Requires computing each particle's inertia as a function of 
the full matter distribution every timestep. High implementation cost, likely 
negligible observable difference at current simulation scales.
---

## External parameter sweep tool

**Concept:** A separate application (not part of the simulation binary) that drives automated parameter sweeps by manipulating `app_setting` values in the database and shelling out to `run`. The simulation itself would need no changes.

**Motivation:** Manual parameter tuning is slow and error-prone. A sweep tool would let the user define a parameter space (ranges, step sizes, combinations) and walk it systematically, collecting results across runs for comparison. Essential before any serious threshold calibration or sensitivity analysis.

**Proposed design:**
- Reads the current `app_setting` table as a baseline
- Takes a sweep spec (parameter name, min, max, step — or discrete list of values)
- For each combination: writes the new values to `app_setting`, invokes the simulation, waits for completion, records the run ID and outcome
- Supports at minimum: single-parameter sweeps, grid sweeps over two parameters, and random sampling over a defined space
- UI to define and preview the sweep space before committing, and to monitor progress

**Key implementation questions:**
- Does each run get its own database, or do all runs share one DB (separated by `run_id`)? Shared DB is simpler; separate DBs make parallel runs safer.
- How does the tool know a run completed successfully vs. crashed?
- What's the output format — a summary table, a new DB table, or just CSV?
- Can sweeps be paused/resumed, or are they fire-and-forget?

**When to build:** After Phase 1 (matter loss / scale factor correlation) is confirmed and threshold tuning becomes the next bottleneck.

---

## GR and QM as phase descriptions, not broken theories

**Hypothesis:** The unification of General Relativity and Quantum Mechanics may be a category error. Water doesn't have a single unified equation covering ice, liquid, and steam — it has the correct equations for each phase. GR and QM may simply be the correct descriptions of different phases of the same underlying reality, not incomplete fragments of a single theory waiting to be merged.

**Why it's interesting:** Both theories are extraordinarily accurate in their own domains. The repeated failure of unification efforts may not indicate the theories are incomplete — it may indicate that demanding one equation cover both phases is the wrong goal. The rip threshold fits naturally into this framing: it's a phase boundary, and the math "failing" at a singularity is the correct signal that the rules are changing, not a flaw to be fixed.

**Things to think through when revisiting:**
- What is the underlying "substance" that transitions between phases? Spacetime geometry? Matter-energy? Something more fundamental?
- What determines which phase a region is in — energy density, curvature, something else?
- Does this framing make any testable predictions, or is it purely interpretive?
- If the rip is a phase boundary, does the simulation produce behavior at that boundary that neither GR nor QM would predict cleanly?

**Gate:** Philosophical for now. Revisit if simulation results show anomalous behavior at rip boundaries that doesn't fit either relativistic or quantum predictions.

---

## Matter phase transition at rip boundaries

**Hypothesis:** Rather than matter crossing into a child geometry, a rip boundary is a phase transition. Matter becomes gravitationally inert — still present in this spacetime, still conserved, but no longer warping space. Analogous to water changing state: same substance, different behavioral rules.

**Why it's interesting:**
- No conservation problem — matter stays in this spacetime
- Dark matter falls out naturally as phase-transitioned matter: gravitationally inert, electromagnetically decoupled, still present and detectable only indirectly
- Expansion driven by reduction in gravitationally active matter fraction rather than matter loss to a child geometry

**Where it broke down:**
- Universe creation is no longer a natural fallout of the mechanism. Under the child geometry model a new universe emerges almost for free — matter crosses, the geometry expands, done. Under phase transition you have to explain what the rip *is* if nothing crosses it, which requires new assumptions that cost more than they save.
- Opens more unresolved questions than it closes at this stage.

**Possible reconciliation:** Phase transition may describe moderate gravitational stress events; child geometry crossing may describe extreme stress. The two mechanisms could coexist at different scales — stellar vs. supermassive black holes already behave differently, and this could be why.

**Gate:** Park until the simulation produces behavior the child geometry model can't account for, or until conservation accounting demands a cleaner story. The child geometry model remains the active hypothesis.

---

## Parameter sweep as empirical phase boundary locator

**Concept:** The parameter sweep tool is not just a tuning instrument — it may be capable of empirically locating the GR/QM phase boundary. If the simulation can reproduce large-scale cosmological behavior from first principles, sweeping the parameter space and observing where macro behavior *transitions* identifies the boundary conditions of that transition. That boundary is the phase transition point between regimes.

**Why it's significant:** You wouldn't be deriving GR or QM from scratch. You'd be doing something more useful — finding the conditions under which the system stops behaving like one and starts behaving like the other. The transition emerges from the data rather than being assumed from theory. This is exactly how phase boundaries are characterized in any other physical system: not derived from first principles, but measured at the point where behavior changes.

**The approach is hypothesis-neutral by design:** The sweep explores the space, the simulation produces behavior, the boundary is wherever the data says it is.

**Early candidate:** The JWST supermassive black hole anomaly sits close to this boundary — quantum-scale rapid collapse producing objects that then dominated large-scale structure. Already on the roadmap and already probing the right regime.

**Gate:** Requires the parameter sweep tool to be built and the core simulation to be reproducing cosmological behavior reliably. Revisit after the sweep tool is operational and the JWST branch produces results.

---

## Ultra-high-energy cosmic rays as parent-geometry infall leakage

**The idea.** Matter falling toward a black hole in the *parent* geometry that does not quite
cross the threshold — near-misses — retains the kinetic energy of that infall. Where the boundary
connects to our universe, such matter could emerge already moving at extreme velocity, with no
local accelerator to account for it. This is a candidate explanation for ultra-high-energy cosmic
rays (the "oh-my-god particle" class) whose energies are difficult to produce with known local
astrophysical accelerators.

**Why it is distinct from SMBH feeding.** The persistence-feeding term (see decisions.md, SMBH
two-sided accounting) is diffuse, bulk, low-velocity matter *entering* the SMBH cell. The cosmic
ray mechanism is the opposite in two ways: it is rare, particle-scale, high-velocity, and it is
matter *leaving* the boundary into neighboring cells. The two may even be in tension (net in vs.
net out), so they must be modeled as separate phenomena, not the same term.

**Why it is parked.** The current grid tracks matter *density* per cell, not particle momentum,
so there is no representation for "high-velocity ejecta with residual infall energy." Modeling
this needs a velocity/momentum carrier. The `structure_particle` table already has velocity_x/y/z
fields, which is the natural eventual home — cosmic-ray events could be spawned as structure
particles emitted from SMBH cells with velocities seeded from a parent-infall energy distribution.

**Falsifiable content.** If implemented, the prediction would be a population of high-velocity
particles originating at SMBH locations, with an energy spectrum set by parent-side infall rather
than local acceleration — testable in shape against the observed UHECR spectrum and against the
spatial correlation of UHECR arrival directions with massive black holes.

**Status.** Idea only. Needs the momentum representation before any implementation. Connects to the
parked dark-matter-as-rip-processed-matter idea (both are "matter that has interacted with a rip
and carries a signature of it").

---

## Stars as near-threshold transients in the pre-collapse band

**The idea.** Between "ordinary cell" and "black hole" there is a density/curvature band where a
gravity well is deep enough to ignite fusion but not yet deep enough to cross the collapse
threshold. Cells in this band are stars. Because the band sits just below collapse, star formation
is a natural by-product of the same gradient that produces black holes — the matter that is on its
way to becoming a black hole but has not arrived yet.

**Why it is a transient ("flash to life").** A star is not a stable end-state in this picture. An
ignited cell either:
1. continues to accrete, crosses the collapse threshold, and becomes a black hole; or
2. burns its matter (fusion → radiation → matter leaving the cell), drops back below the ignition
   band, and goes dark (burnout).

This fork makes stars a temporary population, which fits the simulation's existing transient-driven
character (formation waves, reversal waves). It reuses the accretion-vs-drain competition already
built for SMBHs — only the outcome at the boundary differs.

**Connection to existing results.** Early universe → many cells crossing the gradient quickly → a
burst of star formation coincident with the early black-hole formation wave. This loosely matches
the observed early rapid star formation alongside early black holes, and pairs naturally with the
SMBH branch (overmassive early holes) and the planned galaxy branch (galaxies are made of stars).

**What needs pinning down before implementation.**
- **Ignition band definition:** likely a density window,
  `collapse_density_threshold * lower_fraction < density < collapse_density_threshold`, i.e. a new
  pair of thresholds (or one fraction parameter).
- **Lifetime/burn mechanism:** an ignited cell loses density over time (matter leaving as
  radiation), pushing it toward burnout unless accretion wins and tips it into collapse.
- **Observable / falsifiable content:** star count over time. Prediction: peaks early and correlates
  with the black-hole formation wave. Testable in shape against the run's BH formation timeseries
  and, more loosely, against observed cosmic star-formation history.

**Status.** Idea only. Sequenced after SMBHs; pairs with the galaxy branch. Low modeling cost — it
reuses existing thresholds and the accretion/drain loop, adding an ignition band and a burn term.
---

## Mass as bound energy — implications for rip boundary accounting

**Context:** A spinning black hole losing angular momentum via Hawking radiation necessarily loses mass, because angular momentum carries energy and E=mc² means energy and mass are the same thing. This is not a special case — it's the general rule. Mass is bound energy at rest. A hot object is heavier than a cold one. A compressed spring is heavier than a relaxed one. Binding energy in a nucleus contributes to the mass of the atom.

The full relativistic relation is E² = (mc²)² + (pc)², which collapses to E=mc² for a particle at rest and E=pc for a massless photon. Photons have no rest mass but do carry energy, and therefore gravitate — they bend spacetime and appear in the stress-energy tensor.

**Why it matters for Rip (eventually).** Currently Rip tracks matter density as a proxy for mass, which is correct in spirit. But the physical reality is that what crosses a rip threshold is bound energy in all its forms — rest mass, thermal energy, kinetic energy of bulk flow, gravitational binding energy. If cells ever acquire internal energy states (temperature, bulk velocity, pressure), those contributions would need to be included in the mass that transfers across the boundary, not just the rest-mass density.

**The spin-down case specifically.** If Rip ever models rotating SMBHs (Kerr geometry rather than Schwarzschild), the spin is not a free parameter independent of mass — it's part of the hole's total energy budget. A hole that loses spin loses mass. Any mechanism that bleeds angular momentum (radiation, frame-dragging interactions, mergers) is simultaneously a mass-loss mechanism. The two can't be tracked independently without violating energy conservation.

**Things to think through when revisiting:**
- If cells carry a spin/angular-momentum field, does the rip threshold depend on total energy (rest + rotational) or just rest-mass density? The threshold is currently density-based; in a full Kerr picture it would be energy-density-based, which are the same thing until rotation becomes significant.
- Does angular momentum transfer across the rip boundary along with mass? If so, what does that imply for the spin distribution of SMBHs in the child geometry?
- Hawking radiation from a Kerr hole preferentially carries away angular momentum before mass — the hole spins down first, then shrinks. Is there an analog in Rip where a near-threshold cell bleeds rotational energy before crossing?

**Status.** No implementation needed now. Flag here for when internal energy states or SMBH spin are introduced.

---

## Dark-matter dimple particles crossing rips (dimple as a sink, not just a source)

**The idea.** Once dark matter is carried by particles with real momentum (Tier 2), a particle can
free-fall down a well and arrive at a cell that is — or becomes — an active rip. If the particle is
a genuine moving object, it has no special exemption from the threshold crossing that removes all
other matter: it should cross into the child geometry and leave our spacetime too. Under that
reading the dimple is not only a *source* left behind by past rips, it is also a *sink* — dark
matter that can itself be processed by a later rip.

**Why it's interesting / why it's hard.** This is the consistent position if the particles are real
(a thing that gravitates and moves shouldn't be exempt from the threshold), but it reopens a
coupling the design deliberately firewalls. Matter leaving feeds `matter_delta`, which drives the
scale factor; `total_matter` is non-BH baryonic cells only, so the dimple currently touches `a(t)`
only indirectly (gravity -> structure -> rips) and never enters the expansion arithmetic. Making
dimple particles a sink would route dark-matter mass-loss *back into* `matter_delta`, breaking that
firewall — the dark matter would start driving expansion directly. That is a different universe from
the one the current accounting encodes, so it must be a deliberate, gated choice, never a side
effect.

**Current build behavior.** Particle and rip are decoupled after birth: a dimple particle free-falls
in gravity and never checks whether the cell under it has re-ripped. A particle sitting at (or
falling into) a fresh rip is untouched — it keeps gravitating in our spacetime. This is the "fossil
stays behind" reading, and it is what the firewall currently assumes.

**Why it's parked.** Wiring the sink in now would make the first PM run test two things at once — do
the particles cluster correctly, and does dark-matter re-ripping perturb expansion — with no way to
attribute the result to either. Validate clustering first (the Tier 2 gates), then add the sink as
its own gated step with an explicit A/B on `a(t)`.

**The deep-well connection.** The gravity-derived birth velocity is weakest exactly at well bottoms
(the gradient cancels there), and well bottoms are where rips form. So the particles most likely to
sit still are the ones sitting on top of future rip sites — precisely the population this mechanism
would remove. That makes the question more than academic: if births pile up at well bottoms, the
sink could be a major channel rather than a rare event. The first PM run's dimple panels and
particle distribution show how often particles actually reach deep-well bottoms, which tells us how
much this would even matter.

**Things to think through when revisiting.**
- Does a re-ripped dimple particle add to `matter_delta` (full firewall break — dark matter drives
  expansion) or to a separate channel that is tracked but kept out of `a(t)`? Two very different
  physical claims.
- Is the trigger "particle in a black-hole cell" or "particle in a cell that rips *this step*"? The
  former removes anything sitting in an old well; the latter only removes particles present at the
  moment of a fresh threshold crossing.
- How much dark matter actually leaves per run — rare event or dominant sink? Sets whether this is a
  perturbation or a regime change.
- Conservation bookkeeping: a removed particle's mass leaves the bounded total; confirm the field
  stays bounded and that removed mass is accounted for, not silently dropped (fail-loud).

**Gate condition.** Do not implement until Tier 2 clustering is validated (the three Tier 2 gates
pass). Then add as a separately-flagged mechanism with a measured before/after on the inflation
curve, so the firewall break is observed deliberately rather than discovered.

**Status.** Idea only, surfaced during Tier 2 PM design. Connects to the parked "dark matter as
rip-processed matter" and cosmic-ray-ejecta ideas — all three are "matter that has interacted with a
rip and carries a signature of it."

---

## Self-interacting dark matter (SIDM): particle-particle collisions

**The idea.** Let the dark-matter dimple particles collide with / scatter off each other, instead of
being purely collisionless. Surfaced while looking for something to slow over-streaming particles
down in the Tier 2 PM run.

**Why it is NOT the fix for over-streaming, and why that matters.** Collisionless is the whole point
of Tier 2, not a limitation to patch. Multi-streaming — two streams occupying the same place at
different velocities and passing through each other — is the only thing that produces the Bullet
Cluster offset, the canonical dark-matter smoking gun. Real cold dark matter passed straight through
in the Bullet Cluster *because* it does not self-interact, while the gas shocked and lagged. Adding
collisions turns the dark matter back into something gas-like and destroys the one observation Tier 2
exists to reproduce. If birth velocity is too hot, the fix is a colder birth velocity
(`DIMPLE_BIRTH_VELOCITY_SCALE`), never a new collision force. This entry exists partly to record that
reasoning so collisions are not reached for as a calibration band-aid.

**Why it is still a real, separate idea.** "What if this dark matter is *mildly* self-interacting?"
is a legitimate physics question — it is the SIDM class of models, proposed precisely because purely
collisionless CDM has tensions (cuspy halo cores vs observed cored profiles, too much small-scale
structure). SIDM makes distinct, falsifiable predictions: cored (not cuspy) halo centers, and
collision offsets that differ in a measurable way from the purely collisionless case (the dark matter
lags slightly, between the collisionless lensing peak and the collisional gas). In this sim it would
be a cross-section parameter on the dimple particles, scattering nearby pairs.

**Gate condition.** Do not add until purely collisionless Tier 2 is validated end to end (all three
Tier 2 gates, including a clean Bullet-Cluster offset on a localized colliding pair). Then add the
self-interaction cross-section as its own flagged parameter and A/B it: collisionless vs SIDM should
show *different* halo cores and *different* collision offsets. The value of the comparison is that the
two regimes are observationally distinguishable, so the sim can say which the Rip dark matter
resembles.

**Status.** Idea only, surfaced during Tier 2 birth-velocity calibration. Strictly downstream of a
working collisionless baseline — adding it earlier would mask, not illuminate, the collisionless
dynamics.

---

## Delta / change-only cell storage (decouple grid size from disk)

**The idea.** Stop writing every cell every timestep. A 64³ grid over 5000 steps is ~1.3 billion
`cell` rows and ~134 GB, and it scales as N³ — which is the real wall blocking larger grids (128³ at
full per-step storage is ~1 TB), far more than raw disk space is. Most of those rows are cells that
did **not change** from the previous step (settled voids, quiescent regions). Store periodic full
snapshots plus only the *deltas* in between (or key on "cells that changed this step"), reconstructing
any timestep by replaying deltas from the last full snapshot.

**Why not just save every 25th timestep.** Rejected — it loses data that matters: the exact step a
runaway SMBH forms, the precise contraction-kick timing, any transient that lives and dies between
snapshots. Time resolution must stay at every step for events; the savings has to come from spatial
redundancy (unchanged cells), not temporal downsampling. Delta storage keeps every event at full time
resolution while cutting the bulk that carries no information.

**Why it matters.** This, not the size of the drive, is what gates grid resolution. Cut the per-step
storage by the fraction of cells that are static (likely large in voids) and 128³ becomes affordable
on disk, decoupling "better data" (finer grid) from "runaway DB size." It also speeds I/O across the
board — fewer rows written per step, fewer read on plot.

**Things to think through.** Reconstruction cost (replaying deltas to view an arbitrary timestep vs a
direct indexed read — the `cell(run_id, timestep)` index assumes full rows); what counts as "changed"
(exact equality vs a tolerance, given floats); snapshot cadence (how often a full frame, to bound
replay length); whether the plot scripts read raw rows (they currently do — they would need a
reconstruction layer or a materialized-timestep view); and fail-loud verification that a
reconstructed timestep is bit-identical to what full storage would have held.

**Gate condition.** Not needed until grid size or step count actually forces it — 134 GB on the
current ~900 GB drive is fine for several more 64³ runs. Build it when the next resolution bump is
the goal, *before* increasing the grid (so the bigger grid lands on the compact storage, not the
1 TB full-storage path). Pairs with the grid-resolution increase as a prerequisite, not a successor.

**Status.** Engineering idea, surfaced when the 64³×5000 DB hit 134 GB. Real project, not a quick
toggle; parked until grid growth needs it.

---

## Black-hole registry — nested universes, with current state + per-timestep history

**The idea.** Give every black hole a durable, globally-unique identity: insert a `black_hole`
row at formation and use the key SQLite assigns (`INTEGER PRIMARY KEY`, i.e. the rowid) as its
id. `run.blackhole_id` is then a single FK into that table, naming the exact parent black hole a
run is the interior of. This is the data-model form of the *Universe-inside-a-black-hole*
hypothesis (see that entry): a run is a universe; the column says which black hole, in which
parent universe, it lives inside. Root universe: `blackhole_id = 0`. It also fixes today's
`cell.black_hole_id`, a per-run `Mutex(1)` counter that means nothing across runs ("just a number
that goes up") — now it resolves to a real registry row.

**Two tables, one job each.**
- `black_hole` — **identity + current state**, overwritten in place. `black_hole_id INTEGER
  PRIMARY KEY`, `run_id`, `cell_position_id`, `formation_timestep`, the seed-properties
  (`mass`, `curvature`, `connection_strength`), and `is_active`. One row per BH for its whole
  life; updated each step to "what is this BH right now."
- `black_hole_history` — **per-timestep state while active**, append-only. `black_hole_id`,
  `timestep`, `mass`, `curvature`, `connection_strength`, `matter_density`, `is_active`. One
  row per BH per active step. Flips fall out of the data — a reversal is where `is_active` goes
  true→false between consecutive rows, a re-formation false→true — so there is no separate flip
  log or formed/reverted tag. Grain chosen as per-timestep (not per-flip) because it buys full
  mass/curvature trajectories for the SMBH mass-function work, and it scales with
  BHs x lifetime (millions of rows), a rounding error against `cell`'s billions.
- `is_active` on `black_hole` is a **denormalized cache** of the latest history state — there so
  "is this BH live?" is a flag read, not a `MAX(timestep)`-per-BH lookup mid-run. Write
  discipline: the flag and the history row are written in the same operation, or they drift.

**The two id columns + the 0-sentinel.**
- `run.blackhole_id` `u64` NOT NULL DEFAULT 0 -> `black_hole.black_hole_id`; **0 = root**.
  Rowids start at 1, so 0 is never assigned and is a safe sentinel — keeps NOT-NULL discipline,
  no nullable exception. Precludes an enforced FK (0 -> nonexistent row), but references here
  are conventional (`PRAGMA foreign_keys` off), so nothing is lost.
- `cell.black_hole_id` `u64` NOT NULL DEFAULT 0 -> `black_hole.black_hole_id`; **drop the
  `Option<u64>`**. Five Rust sites (`cell.rs` field + default, `black_hole.rs` set + revert,
  `galaxy.rs` absorption); the write in `sqlite_provider.rs` may need `as i64` (rusqlite
  `ToSql`). No SQL/plot breakage — nothing keys on NULL-ness. Existing `rip_data.db` keeps the
  nullable column but stays valid (code writes 0, never NULL); only fresh DBs from the template
  carry the NOT NULL constraint.

**Write path / parallelism.** `set_as_black_hole` runs inside the rayon cell passes, so a
synchronous per-collapse insert there is a contention + correctness hazard. Do all registry
writes at the serial point between passes, batched: formation = insert `black_hole` rows,
`last_insert_rowid()` -> stamp cells; each step = overwrite each active BH's `black_hole` row +
append its `black_hole_history` row.

**OPEN QUESTION — identity vs liveness on `cell.black_hole_id` (settle before the revert edit).**
Consolidating revealed a conflict between two decisions made several turns apart:
- (A) migrate `is_black_hole` readers -> `black_hole_id != 0`, then eventually drop the boolean;
- (B) reuse a BH's row on re-collapse (don't mint a new row per episode).
These disagree on what `black_hole_id` means when a cell reverts:
- If the cell **keeps** its id through reversal (so re-collapse re-finds its row off the cell),
  then `black_hole_id != 0` includes dormant cells -> it is *not* equivalent to `is_black_hole`,
  so the boolean **cannot** be dropped and plots must keep filtering on `is_black_hole`. (A) dies.
- If the cell **clears** its id on reversal (0 = not currently live), then
  `is_black_hole <=> black_hole_id != 0` holds and (A) survives — but reuse-the-row can no longer
  read the old id off the cell, so it must find the dormant row another way: look it up by
  `(run_id, cell_position_id)`, e.g. an in-memory `cell_position -> black_hole_id` map kept at the
  serial point.
- Third option: a **new** `black_hole` row per collapse episode (no reuse) — simplest writes, but
  one physical location accrues many ids and "this BH's history" gets fuzzy.
- This going to use a `black_hole` table with an is_active field and `black_hole_history` will leave 
  all the links in place and change the value of IsActive as needed.

**Reversal physics (independent of bookkeeping).** `revert_black_hole` already dumps the residual
`matter_density` back into `total_matter` — the contraction kick. Conservation hazard for the
nested case: if the BH seeded a child universe, mass that left into the child must **not** return on
revert, or it exists in both the child and the re-expanded parent (double count). Check at each
true->false transition.

**Child seeding (the actual payoff).** Spawn a child run whose matter budget / initial geometry
derives from the parent BH's `mass` and `curvature` — the two-sided SMBH accounting, parent inflow
as the child-side boundary source. The columns are the easy part; this is the design effort.

**Gate condition.** The schema (two tables, both id columns, `is_active`, history) is cheap and can
land after the gas-pressure/drag issue — but the identity-vs-liveness question above must be settled
first, since it sets the `revert` behavior. The *payoff* (spawning a child, re-entering "the same"
BH) is gated on **reproducible runs**: you can't re-enter a BH in a run you can't regenerate, and the
physics RNG is currently `thread_rng()` (grid/particle/in-loop draws), not seeded from the recorded
`seed`. Build order: determinism fix -> registry tables + columns -> child-seeding.

**Status.** Design consolidated across the `NUM_RUNS`-removal discussion; `cell.black_hole_id`
already exists as a placeholder counter. Parked: schema shovel-ready after gas once the
identity/liveness question is resolved; spawn mechanic waits on determinism + Tier 2.
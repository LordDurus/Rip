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

**Things to think through when revisiting:**
- What's the boundary in this picture? The cosmological horizon? The parent black hole's horizon? The rips themselves?
- Does the simulation actually produce a holographic encoding, or is that an interpretation laid on top?
- How does information get *out* (or does it)? Is it accessible in principle, or only preserved in a formal sense?
- Connection to AdS/CFT and existing holographic frameworks — does this fit, extend, or conflict?
- If rips store information holographically, does that constrain what rips can do or where they can form?

---

## Universal constants as a function of parent geometry

**Hypothesis:** The fundamental constants of a universe (gravitational constant, speed of light, dark matter ratio, etc.) aren't arbitrary — they're determined by the initial geometry of the matter distribution that formed the parent black hole. Different pre-collapse geometries in the parent universe produce different physics in the resulting child universe.

**Why it's interesting:** This provides a *mechanism* for the multiverse explanation of fine-tuning, rather than treating "many universes with random constants" as a brute postulate. The variation in constants becomes a consequence of the variation in pre-collapse matter arrangements — something the simulation can actually model and test, since you're already parametrizing both initial geometry and physics constants. If certain geometry → constant relationships are stable across runs, that's a real, testable mapping.

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
- Does the rip field also need long-range treatment, or is it conceptually local? Probably depends on which decay mechanism is chosen.
- The `cell.gravity_x/y/z` storage stays the same; only the computation changes.
- Existing tuning (curvature_threshold, density thresholds, weights) will likely need recalibration after the switch.

---

## Cyclic universe with leaky boundaries

**Hypothesis:** The universe undergoes damped cycles driven by the rip field and black hole formation/healing. Each cycle is smaller than the last due to matter lost beyond gravitational reach during expansion.

**The cycle:**
1. Rip field drives inflation, black holes form, matter drains into rips
2. Rip field weakens, black holes slowly heal (self-healing decay mechanism), matter returns
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

**Motivation:** Manual parameter tuning is slow and error-prone. A sweep tool would let you define a parameter space (ranges, step sizes, combinations) and walk it systematically, collecting results across runs for comparison. Essential before any serious threshold calibration or sensitivity analysis.

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
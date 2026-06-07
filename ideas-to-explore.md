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

**When to build:** After Phase 1  (TBD) (matter loss / scale factor correlation) is confirmed and threshold tuning becomes the next bottleneck.
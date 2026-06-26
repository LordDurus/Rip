# Physics Problems & Fixes

A log of **physics / dynamics failure modes** in Rip: what went wrong, why (the
modeling reason), and what fixed it. Scope is deliberately narrow — only problems
about the *physics* and the fields it produces. Code, database, tooling, and
diagnostic-script issues are out of scope and belong elsewhere (e.g. the
Infrastructure section of `decisions.md`).

This is a companion to the other two docs, not a replacement:
- `decisions.md` — *why* each modeling choice was made (Decision / Reason / Consequence).
- `results.md` — *what the simulation produced* and why it matters.
- this file — *what broke and how it was fixed*, so a failure mode isn't rediscovered.

Each entry: **Symptom → Cause → Fix → Status/Lesson.**

---

## 0. The recurring bug class: a cap whose denominator depends on what it caps

This is the single most repeated physics bug in the project — it has appeared at
least three times, in unrelated subsystems, always with the same shape. It leads
this file because recognizing the *shape* is worth more than any individual fix.

**The shape.** A quantity is bounded by a cap or budget. The cap's denominator (or
the budget it splits) is computed from a number that *includes, or shrinks with,*
the very quantity being capped. As the capped quantity grows, the constraint
weakens, which lets it grow more — a self-reinforcing loop ending in runaway (or,
with the sign flipped, collapse).

**Instance 1 — rip drain rate.** An early drain term whose rate was coupled to the
quantity it was meant to limit; the coupling let the drain either run away or stall.

**Instance 2 — phantom additive feedback in `apply_gravity_interaction`.** An
additive feedback path that reinforced itself; the function was later removed
entirely (see `decisions.md`, Implementation).

**Instance 3 — SMBH competition cap double-subtraction (galaxy-phase2).** The
per-galaxy baryonic budget was computed as `total_mass[i] - smbh_mass[i]`. But
`find_galaxies` already accumulates `total_mass` from non-BH cells only — SMBH mass
was never in that sum, so subtracting it was a *second* subtraction. As an SMBH
grew, the denominator shrank toward zero; once `smbh_mass >= total_mass` the budget
clamped to zero and hit the `baryonic_mass <= 0 { continue }` guard, which skips the
cap entirely. The biggest holes were precisely the uncapped ones: in-galaxy max mass
climbed 10^10 → 10^11 → 10^16 and drove `gravity_magnitude_avg` to ~10^28.

- **Fix:** `let baryonic_mass = total_mass[i].max(0.0);` — `total_mass` is *already*
  the budget. One line.
- **Consequence:** in-galaxy max SMBH mass returned to ~10^1–10^2 (transient 10^3–10^6
  in just-merged galaxies that relax back); the mass function lost its 10^16 tail and
  now tops near 10^5–10^6 — still heavy-tailed (JWST-overmassive regime) but bounded.

**Lesson (standing principle).** A cap's denominator must be *independent of the
thing being capped*. Before adding any budget/cap, ask: does this denominator shrink
as the capped quantity grows? If yes, it's this bug.

---

## 1. Inflation was at risk of being "coded in" rather than emergent

**Symptom.** Early expansion machinery could have made the central hypothesis test
(matter-loss drives expansion) trivially true regardless of the actual dynamics.

**Cause.** Three engineered shortcuts: a hard expansion cutoff, a seeding height
bias, and a one-way matter delta (`.max(0.0)`, so the scale factor could only ever
increase). Any of these "codes the answer" — a mechanism tuned to expand will expand.

**Fix.** Removed the hard cutoff and the seeding height bias. Made the matter delta
**symmetric**: matter loss → expansion, matter gain → contraction, with `a(t)`
floored at its initial value (matter cannot un-exist) but no ceiling. The test is now
fair; during the inflation epoch matter loss dominates anyway, so expansion still
wins — but it wins honestly.

**Status/Lesson.** With the shortcuts gone, an inflation-like profile (rapid early
expansion, smooth deceleration, graceful exit) emerged *without being targeted*.
Recorded principle: a result the simulation was **not** tuned to produce is
higher-quality evidence than one it was designed for. Evaluate future results on the
same criterion.

---

## 2. The diffuse rip drain masked the only channel with a reversal

**Symptom.** Black-hole formation/reversal (the only mechanism that can produce
*contraction*) was invisible in `a(t)`; expansion looked like it came entirely from a
uniform leak.

**Cause.** At `RIP_DRAIN_RATE = 1.25e-6` the diffuse drain is a strong, uniform,
**one-way** matter sink. It removed essentially all matter over a run and
single-handedly set `a(t)`, drowning out the black-hole channel.

**Fix.** Lowered the drain ~100× to `1.25e-8`, demoting it to a slow background drift
(~6%/run) so formation/reversal drives `a(t)`. Separately, removed the in-place
`accretion` growth term; conservative transport replaced it. Clean split now: **drain
removes matter from the universe, transport redistributes what remains.**

**Status/Lesson.** This is the change that made contraction visible. A strong uniform
one-way term will always dominate a weaker but more *interesting* channel — keep
background sinks slow enough that the dynamics you're testing can be seen over them.

---

## 3. Gravity-sourcing the curvature killed all collapse

**Symptom.** Nothing collapsed into black holes; the matter field stayed smooth.

**Cause.** Setting `curvature = gravity_curvature_coupling · |g|` drove curvature to
~1e-14 — twelve-plus orders of magnitude below the `0.08` collapse threshold — so no
cell could ever cross it. It also coupled curvature to `transport_rate` (curvature ∝
gravity ∝ concentration ∝ transport_rate), making the two knobs non-independent and
the threshold impossible to calibrate.

**Fix.** Reverted curvature to its random seed (`rng 0.0..0.1`), left untouched in
the loop. The seed is transport-independent: ~20% of cells exceed 0.08, and dense
knots among them collapse.

**Status/Lesson.** **Trap to remember:** when reverting, remove *only* the curvature
line from the gravity write-back loop. Commenting out the whole block also kills the
`gravity_x/y/z` assignments, which zeroes transport and accretion (every cell's
`l1 <= 0` guard fires → smooth, unclumped matter). Two knobs that feed each other
can't both be calibrated; keep the collapse threshold's input independent of the flow
rate.

---

## 4. Swapped transport axis-pairing → diagonal field artifacts

**Symptom.** Diagonal-stripe / stacked-sheet artifacts in *every* field.

**Cause.** The gravity-to-axis pairing in transport was rotated relative to the FFT's
array-dimension order. A rotated mapping advects mass transversely to the true
gradient — the diagonal (rather than axis-aligned) stripe is the tell that it was an
x↔y swap in the row–col plane, not a single-axis flip.

**Fix.** Straight pairing `(gh, gw, gd) = (gravity_x, gravity_y, gravity_z)`, matching
the FFT order (dim0→x, dim1→y, dim2→z).

**Status/Lesson.** Field artifacts have geometric signatures: *diagonal* stripes mean
a rotation/transpose; *axis-aligned* banding means a single-axis flip or a boundary
issue. Read the artifact's geometry to localize the bug.

---

## 5. The dark-matter dimple was a space-filling fog, not a clustering halo

**Symptom.** The `rip_dimple` projection was a near-uniform, space-filling fog with
mild texture — the *opposite* of the sharply clumped matter field.

**Cause.** The deposit-everywhere + uniform-dilution + pinned-to-cell design records
where rips have *ever* happened (≈ everywhere over a long run), not where structure
*is now*. A uniform mass component (a) exerts no net internal force by symmetry, so it
binds nothing differentially, and (b) produces no lensing, because
convergence/shear need density *contrast*, not mere presence. A fossil records the
past; a halo has to track the present.

**Fix (Tier 1).** `apply_dimple_transport`: advect `rip_dimple` down the *total*
gravity gradient with a conservative two-pass scheme (collisionless — every cell
participates, flux crosses BH cells freely). This clusters the dimple into wells and
drains voids, creating the contrast lensing needs, while staying conservative so the
boundedness argument holds (dilution remains the only sink). `DIMPLE_TRANSPORT_RATE =
0.025`; **`= 0` recovers the static fossil exactly** (a clean reversible A/B toggle).

**Status/Lesson.** Cost recorded explicitly: the dimple is no longer positionally
frozen (still mass-decoupled at deposit). **Known limit:** an over-damped,
single-velocity grid field settles into wells and *cannot multi-stream*, so Tier 1
yields halos but **not** the Bullet-Cluster pass-through offset — that needs the
Tier 2 collisionless-particle representation.

---

## 6. Gas stability was misattributed to thermal pressure (bullet-cluster-phase1b)

**Symptom.** Gas density looked nicely bounded under collapse; this was read as
thermal-pressure (Jeans) support working.

**Cause.** There was no thermal-pressure term. `GAS_SOUND_SPEED` existed only in an
untracked plot script and a modified `decisions.md` — not in the Rust source or
`template.db`. The bounding was actually the **rip-drain limit cycle**: gas that gets
dense enough crosses the rip threshold, is reclassified as a black hole, and is
removed from `matter_density` — so the *maximum* drops, accidentally, with no pressure
involved.

**Fix.** Implemented isothermal thermal pressure `a = -c_s² ∇ρ / ρ` in Pass 1 of
`apply_gas_momentum` (central differences on `matter_density` with periodic wrap),
gated behind `GAS_PRESSURE_ENABLED` so the disabled path is byte-identical to the
validated rip-drain curve (a true null test). A sound-Courant clamp
`(|v| + c_s)·dt ≤ CFL` keeps it stable. With pressure on, max matter density dropped
from ~3000 to ~156 — Jeans support active without tripping the Courant freeze.

**Status/Lesson.** "The field is bounded" does not imply "the mechanism I think is
bounding it is the one bounding it." Always identify *which* term is doing the work
(here, confirmable by toggling pressure off and recovering the identical rip-drain
curve). **Open watch item:** BH-neighbor density is currently clamped to local density,
making a reflecting (no-flux) wall at rip sites — this can raise pressure walls / ring
artifacts in the dimple field. Proposed one-line fix: treat BH neighbors as
zero-density (outflow) instead of reflecting.

---

## Open watch items (physics, not yet resolved)

These are under observation, not fixed — listed so they're not lost.

- **`total_dimple` rising while `max_dimple` stays flat.** The dimple is spreading to
  more cells (a rising `dimpled_cells` count), not blowing up per cell. The Tier 1
  gate is *`total_dimple` bounded*, so a flat max is not sufficient evidence. Confirm
  it saturates over a full 5000-step run as the dimple fills the grid. (Now plotted
  directly by `plot_stability.py`, with a final-quarter "still rising vs leveled off"
  check.)

- **Bullet-cluster first-pass offset with drag off (pressure-only quadrant).** Does a
  measurable gas–dimple lag develop at first closest approach, or do the clumps
  free-fall through each other too fast for pressure alone to produce one? Under
  measurement via the first-pass offset diagnostic; the offset at the exact minimum is
  smeared by window overlap, so the clean read is a few frames before merge.

- **Orphan SMBH ceiling (~10^6).** Read as a self-limiting equilibrium (growth tied to
  local curvature in a thinning void), *not* a runaway. Re-check on a 10000-step run:
  if `max_orphan_mass` climbs past ~10^7 rather than holding near 10^6, the
  self-limiting read is wrong and there's an unbounded source (e.g.
  `smbh_connection_strength` frozen at formation rather than recomputed against
  current local curvature).
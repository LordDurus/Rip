## Bullet collision: binding tension, the v=10 clean offset, and making velocity emergent

<details>
<summary>A matured, dimple-rich box binds the clumps far more tightly than the thin-dimple sweep predicted -- velocity, not box size, is the lever that unbinds them</summary>

**Decision.** The Bullet collision runs at `BULLET_INITIAL_VELOCITY = 10` on the
existing 80^3 grid. The box size is NOT increased.

**Reason.** The t=0-kick velocity sweep (thin dimple field) showed clumps
unbinding at v >= 6. But when the same velocities were applied to a matured
two-phase box (rip epoch complete, in-halo dark fraction ~0.5), the clumps
stayed BOUND: at v=7 they collided and rattled in a tight 2-10 cell sawtooth,
never re-separating, and the post-pass diagnostic hit the box-size wall on
every window. The extra gravitating mass that makes the offset measurable --
the dark fraction we spent the epoch maturing to get -- is the same mass that
recaptures the clumps after the pass. Velocity selections from a thin-dimple
sweep do not transfer to a thick-dimple run because the binding is different.

Raising the kick to v=10 resolved it directly: the clumps unbound, re-separated
to a clean 54.95-cell crest at t=8408 (mid-run, far past 2*window), and the
gas-dimple offset came back coherent -- left +9.1, right +15.2 cells, same sign,
comparable magnitude -- rather than the overlap-regime garbage (+2 vs -32) that
bound runs produced. In-halo dark fraction 0.47/0.53. This is the first clean,
properly-sampled Bullet offset measured on a dark-matter-dominated box.

**Consequence.** Box size was never the limit for the AFTERMATH separation --
velocity was. The disk-space / larger-box work stays parked. Every prior
suspected limit (resolution, checkerboard, kick timing, velocity) is now
eliminated, and a clean offset exists on 80^3. NOTE the sign: both clumps read
"gas leads dimple" in col; whether that is the correct Bullet sign (gas
trailing dark matter) depends on each clump's direction of travel at t=8408 and
must be checked against the trajectory before the sign is asserted -- the
magnitude and coherence are solid regardless.
</details>

<details>
<summary>v=10 is currently a TUNED parameter; making it emerge from clump mass and separation is the next step (avoids "coding the answer")</summary>

**Decision (open / next step).** Treat the current `BULLET_INITIAL_VELOCITY = 10`
as a tuned free parameter and a known limitation, not a physical result. The
target is to make the collision velocity EMERGE from the model's own state
rather than being dialed in.

**Reason.** v=10 was chosen because v=7 stayed bound and v=10 did not -- a value
fitted to the desired outcome, which is the same "coding the answer" smell the
project treats as a falsification risk elsewhere. In the real Bullet Cluster the
collision velocity is not free: it is the infall velocity two clusters reach by
falling together under gravity from cosmological separation (~4700 km/s at
pericenter for ~1e15 Msun clusters), set by energy conservation from the masses
and initial separation -- derived, not chosen.

Three paths, in increasing physical honesty and cost:
1. **Gravity sets it (correct, expensive).** Start the clumps at rest, far
   apart, and let mutual gravity accelerate them into collision; contact
   velocity emerges from clump mass (dimple + gas) and separation. Gated on a
   LARGER BOX -- not for aftermath room, but so the clumps have distance to
   accelerate to supersonic before contact (periodic images fight the
   attraction in 80^3). This reframes the box-size question: the box matters for
   letting infall velocity emerge, not for showing separation.
2. **Derive the kick from clump state (middle ground, preferred next).** Keep
   the kick, but compute its magnitude from the infall/escape velocity implied
   by the actual clump mass and separation at kick time (v ~ sqrt(2*G*M/r) from
   the dimple+gas mass the model already tracks) instead of reading a fixed
   setting. v stops being tuned: it becomes a quantity the model computes from
   its own state, and it self-corrects if the masses change. Falsifiable
   prediction: required velocity should scale with dimple mass (~sqrt(M)) --
   testable by running two dark-fraction boxes and checking the derived v tracks.
3. **Anchor the setting to observation (stopgap).** Keep v as a setting but
   document it against the real ~Mach 3+ Bullet regime, as SMBH probability was
   anchored to the observed galaxy count. Defensible but still a chosen number.

**Consequence.** Option 2 is the intended next move: modest code change, removes
the tuning, and yields a falsifiable mass-velocity scaling. Option 1 is the
long-term "correct" version, gated on the larger box, and is the real reason the
box-size card might eventually be justified. Until one of these lands, any claim
that the Bullet offset is a parameter-free prediction is overstated -- the
offset is real and clean, but the velocity that produces it is still an input.
</details>
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
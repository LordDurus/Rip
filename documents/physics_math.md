# Core Math (draft)

The governing equations and numerical schemes behind Rip's physics, in one place.

**This is a draft kept deliberately short** — the open question is whether a math doc
earns its keep alongside `decisions.md` (which already carries the reasoning) or just
duplicates it. Expand only the parts that turn out to be referenced often; delete the
rest. Code-level detail (struct layouts, SQL, indexing) is out of scope by design.

Notation: `ρ` = `matter_density` (non-BH cells; BH cells carry the `1e30` sentinel and
are excluded from every field sum), `φ` = gravitational potential, `g = -∇φ`, `a(t)` =
cosmological scale factor, `D` = `rip_dimple` (the dark-matter proxy field).

---

## Gravity — FFT Poisson solver

Solve

    ∇²φ = 4πG ρ_src

in Fourier space via three 1-D FFT passes (one per axis), periodic boundary
conditions. The `k = 0` mode (mean density) is forced to zero — the **Jeans swindle** —
because the self-gravity of an infinite uniform medium diverges; this is standard in
cosmological N-body. The source includes the dimple's own gravity:

    ρ_src = matter_density + rip_dimple

so the dark-matter proxy gravitates on the same footing as baryons. Acceleration is
`g = -∇φ`, evaluated by finite differences with the same periodic wrap.

---

## Matter transport and drain

Matter moves by **conservative, downhill-only** advection: a two-pass scheme flows mass
down the gravity gradient with no back-pressure, so the rate sets the *timescale* of
concentration, not the endpoint. On top of that, each non-BH cell loses matter to a
one-way rip drain:

    Δρ_drain = -RIP_DRAIN_RATE · rip_strength · ρ

Drain removes matter from the universe; transport only redistributes what remains.
(`RIP_DRAIN_RATE = 1.25e-8` keeps the leak slow — see physics-problems.md §2.)

---

## Collapse to a child geometry (black hole / rip)

A cell collapses when local geometry crosses fixed thresholds — principally
`curvature > CURVATURE_THRESHOLD` (0.08), with density thresholds gating formation.
On collapse the cell's `matter_density` is set to the `1e30` sentinel and the cell is
excluded from all field calculations and from `total_matter`.

---

## Expansion — symmetric scale-factor response

The scale factor responds to the change in non-BH matter, **symmetrically**:

    Δ(total_matter) < 0  →  expansion
    Δ(total_matter) > 0  →  contraction

with `a(t)` floored at its initial value (no un-existing) and no ceiling. `total_matter`
counts non-BH cells only, which firewalls the inflation accounting from the dimple and
from BH interiors. Matter that crosses into child geometries leaves normal spacetime and
drives expansion; reversion (BH healing) returns matter and drives contraction.

---

## The dimple — clustering dark-matter proxy

`rip_dimple` is a gravitating residual that is **mass-decoupled at deposit** (the GR
break) but mobile. Tier 1 transport advects it down the *total* gravity gradient
(`matter_density + rip_dimple`) with a conservative, collisionless two-pass scheme;
dilution is the only sink, so the total stays bounded. Clustering produces the density
*contrast* that lensing requires. Diagnostics: `r(dimple, baryon)` (≈0 for a uniform
fog, rising positive as the dimple co-locates with structure) and the dimple–baryon
centroid offset.

**Limit:** a single-velocity grid field cannot multi-stream, so it yields halos but not
the Bullet-Cluster pass-through offset; that needs Tier 2 collisionless particles.

---

## Gas thermal pressure (bullet-cluster branch)

Isothermal equation of state `P = c_s² ρ` gives the pressure acceleration

    a_pressure = -c_s² ∇ρ / ρ

applied in Pass 1 of the gas momentum update alongside gravity, using central
differences on `matter_density` with periodic wrap. Stability is enforced by a sound
Courant condition

    (|v| + c_s) · dt ≤ CFL

with the L1 speed, consistent with the advection flux cap. Gas is collisional and
pressure-supported; the dimple (dark-matter proxy) is collisionless — the configuration
that, in a head-on collision, should leave the gas lagging the dark matter.

---

## Bullet kick velocity — making the collision speed a derived quantity

`BULLET_VELOCITY_MODE` selects where the collision speed comes from:

| mode | source | status |
|---|---|---|
| 0 | `BULLET_INITIAL_VELOCITY` verbatim | a **tuned** free parameter (v=10 was found because v=7 left the clumps bound) |
| 1 | derived from the box's own mass and separation | removes the tuning |
| 2 | start at rest, let gravity accelerate | not implemented — needs a bigger box |

**Mode 1.** Two bodies falling from rest at separation `r_start` reach, at separation
`r_contact`, a relative speed set by energy conservation:

    v_rel² = 2 G M (1/r_contact − 1/r_start)

Each clump carries half the closing speed, so the per-side kick is `v_rel / 2`, scaled
by `BULLET_VELOCITY_MULTIPLIER` (default 1.0 — no effect; a knob to reach for
deliberately, not a hidden fudge). `r_start`, `r_contact` and `M` are **measured from
the grid** at kick time, not read from the seeding settings, so the number is right
whether the clumps were Gaussian-seeded or drifted first. `r_contact = σ_left + σ_right`
(excess-weighted RMS radii; cores meeting) is a modeling choice and the most sensitive
input, since it sets the `1/r` blow-up.

Two corrections are required, and neither is optional:

**Effective G.** `compute_gravity_fft` uses the raw integer mode index as the
wavenumber (`get_wave_number` returns `i`, not `2πi/N`). Matching the sim's solve

    φ̂ = −4πG ρ̂ / |m|²,   ĝ = −i m φ̂

against a physically normalised solve (`k = 2πm/N`, cell spacing 1) gives
`4πG = 2 G_eff N`, hence

    G_eff = 2π G / N        (cubic grid only)

So the gravity the sim *applies* is that of `G_eff`, not of `app_settings.gravity`. At
N=80, `G_eff ≈ 0.0785 G` — ~12.7× smaller. Since `v ∝ √G`, using the raw setting would
overstate the infall speed by ~3.6×. This is not a solver bug — it is a self-consistent
rescaling absorbed into whatever `gravity` was tuned to — but it is fatal to any velocity
derived analytically rather than by the solver. On a **non-cubic** grid the sim's `k²` is
not proportional to the true `k²` at all, so mode 1 refuses to guess and falls back.

**Only contrast gravitates.** The `k = 0` mode is zeroed (Jeans swindle), so the mean
density exerts no force: what pulls the clumps together is each clump's **excess over the
box mean**, not its total mass. Summing `(ρ − ρ̄)` over half-boxes is degenerate (it sums
to zero over the whole box), so `M` is the sum of the **positive** excess only — the
overdense material that actually attracts. `ρ = matter_density + rip_dimple`, i.e. exactly
the source term handed to the Poisson solver, so `M` and `G` are the same accounting the
gravity obeys.

**Honest limits.** This is an idealised two-body number, not the true infall this periodic
box would produce: periodic images pull each clump *backward* (so the derived `v` is an
upper bound on gravity's own answer), and expansion works against the approach and is not
in the formula. Mode 1 removes the *tuning*, not the *idealisation*. If the derived `v`
leaves the clumps bound, that is a **real finding** — gravity from this separation cannot
unbind them in this box — and it is the argument for mode 2 plus a bigger box, not a
reason to reach for the multiplier.

**Units caveat (open question).** `GRAVITY` is set to the SI value `6.674e-11` while
density, length and time are arbitrary code units. The dimensionless gravitational
strength that results is therefore very small, and mode 1's derived `v` is expected to be
correspondingly tiny. If it is, that is not a formula error — it says self-gravity is
numerically negligible for the gas in the current unit system, which would independently
explain why passive infall never collides (30.0 → 25.5 cells over 7,000 steps). Calibrating
the unit system (what is one cell in metres, one step in seconds, one density unit in
kg·m⁻³?) is the prerequisite for gravity-derived velocities to mean anything.

---

## Gas–dimple offset (collision diagnostic)

Along the collision axis, project each field onto columns (sum over the other two
axes). For each clump, take a density-weighted centroid in a window around its peak —
weighting by `matter_density` for the gas centroid and by the positive part of
`rip_dimple` for the dark-matter centroid. The per-clump **offset** is `gas_centroid −
dimple_centroid`; a lag is the Bullet-Cluster signature. **First closest approach** is
the first separation minimum *after* separation has genuinely dropped below a fraction
of its initial value (so pre-collision plateau noise is rejected). At the exact minimum
the two windows overlap and the offset smears, so the trustworthy read is a few frames
before merge.
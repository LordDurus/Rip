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
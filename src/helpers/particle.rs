use crate::database::entities::cell::Cell;
use crate::database::entities::structure_particle::StructureParticle;
use crate::helpers::particle::f64::consts::PI;
use rand::Rng;
use rayon::prelude::*;
use std::f64;

pub fn initialize_particles(positions: &mut Vec<(f64, f64, f64)>, velocities: &mut Vec<(f64, f64, f64)>) {
    let mut rng = rand::thread_rng();
    for i in 0..positions.len() {
        let theta = rng.gen_range(0.0..2.0 * PI);
        let phi = rng.gen_range(0.0..PI);
        let r = rng.gen_range(0.8..1.2);

        let x = r * phi.sin() * theta.cos();
        let y = r * phi.sin() * theta.sin();
        let z = r * phi.cos();

        let velocity_x = rng.gen_range(-0.05..0.05);
        let velocity_y = rng.gen_range(-0.05..0.05);
        let velocity_z = rng.gen_range(-0.05..0.05);

        positions[i] = (x, y, z);
        velocities[i] = (velocity_x, velocity_y, velocity_z);
    }
}

#[inline(always)]
pub fn apply_gravity_to_particle(particle: &mut StructureParticle, gravity: (f64, f64, f64), timestep: f64) {
    particle.velocity_x += gravity.0 * timestep;
    particle.velocity_y += gravity.1 * timestep;
    particle.velocity_z += gravity.2 * timestep;

    for coord in [&mut particle.velocity_x, &mut particle.velocity_y, &mut particle.velocity_z] {
        if !coord.is_finite() {
            *coord = 0.0;
        }
    }

    particle.position_x += particle.velocity_x * timestep;
    particle.position_y += particle.velocity_y * timestep;
    particle.position_z += particle.velocity_z * timestep;
}

#[inline(always)]
pub fn map_particle_to_cell(x: f64, y: f64, z: f64, grid_width: usize, grid_height: usize, grid_depth: usize) -> Option<(usize, usize, usize)> {
    if !(x >= -1.0 && x <= 1.0 && y >= -1.0 && y <= 1.0 && z >= -1.0 && z <= 1.0) {
        return None;
    }

    let col = ((x + 1.0) / 2.0 * grid_width as f64).floor() as usize;
    let row = ((y + 1.0) / 2.0 * grid_height as f64).floor() as usize;
    let layer = ((z + 1.0) / 2.0 * grid_depth as f64).floor() as usize;

    if col < grid_width && row < grid_height && layer < grid_depth {
        Some((col, row, layer))
    } else {
        None
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tier 2: collisionless dark-matter particle-mesh helpers.
//
// Dark matter is carried by particles that free-fall in the FFT gravity field.
// Each step they are pushed by the gathered gravity (CIC), then their mass is
// scattered (CIC) back onto the grid `rip_dimple` field, which sources the
// Poisson solve and feeds every existing diagnostic (lensing, CMB, save). Using
// CIC symmetrically for scatter and gather makes the self-force cancel. All
// gated behind use_dimple_particles; with it false none of this runs.
// ─────────────────────────────────────────────────────────────────────────────

/// Cell-index triple -> particle position in [-1,1]^3 (cell center). Inverse of
/// the cell mapping, so a freshly spawned particle maps back to its birth cell.
#[inline(always)]
fn cell_center(h: usize, w: usize, d: usize, gh: usize, gw: usize, gd: usize) -> (f64, f64, f64) {
    (
        (h as f64 + 0.5) / gh as f64 * 2.0 - 1.0,
        (w as f64 + 0.5) / gw as f64 * 2.0 - 1.0,
        (d as f64 + 0.5) / gd as f64 * 2.0 - 1.0,
    )
}

/// CIC support along one axis: returns the two bracketing cell indices (periodic)
/// and the fractional offset in [0,1) of `pos` (in [-1,1]) from the lower one.
#[inline(always)]
fn cic_axis(pos: f64, n: usize) -> (usize, usize, f64) {
    let nf = n as f64;
    let cx = (pos + 1.0) * 0.5 * nf - 0.5; // continuous cell-center coordinate
    let base = cx.floor();
    let frac = cx - base;
    let i0 = (base.rem_euclid(nf) as usize) % n; // periodic wrap
    let i1 = (i0 + 1) % n;
    (i0, i1, frac)
}

/// Wrap a coordinate periodically into [-1, 1). Non-finite -> 0.
#[inline(always)]
fn wrap_unit(v: f64) -> f64 {
    if !v.is_finite() {
        return 0.0;
    }
    (v + 1.0).rem_euclid(2.0) - 1.0
}

/// Trilinear (CIC) gather of the gravity vector from the 8 cells bracketing a
/// particle. Must use the same kernel as the scatter so the self-force cancels.
#[inline]
fn gather_gravity_cic(grid: &[Vec<Vec<Cell>>], i0: usize, i1: usize, fx: f64, j0: usize, j1: usize, fy: f64, k0: usize, k1: usize, fz: f64) -> (f64, f64, f64) {
    let nodes = [
        (i0, j0, k0, (1.0 - fx) * (1.0 - fy) * (1.0 - fz)),
        (i1, j0, k0, fx * (1.0 - fy) * (1.0 - fz)),
        (i0, j1, k0, (1.0 - fx) * fy * (1.0 - fz)),
        (i0, j0, k1, (1.0 - fx) * (1.0 - fy) * fz),
        (i1, j1, k0, fx * fy * (1.0 - fz)),
        (i1, j0, k1, fx * (1.0 - fy) * fz),
        (i0, j1, k1, (1.0 - fx) * fy * fz),
        (i1, j1, k1, fx * fy * fz),
    ];
    let (mut gx, mut gy, mut gz) = (0.0, 0.0, 0.0);
    for (a, b, c, wt) in nodes {
        let cell = &grid[a][b][c];
        gx += cell.gravity_x * wt;
        gy += cell.gravity_y * wt;
        gz += cell.gravity_z * wt;
    }
    (gx, gy, gz)
}

/// Birth position (cell center) and velocity (local gravity * scale) for a
/// dark-matter particle spawned at a rip site. Gravity-derived so nothing is
/// born at exactly rest; the struct itself is built by the caller so its field
/// types match the entity exactly.
pub fn dimple_birth_state(h: usize, w: usize, d: usize, gh: usize, gw: usize, gd: usize, gravity: (f64, f64, f64), birth_velocity_scale: f64) -> ((f64, f64, f64), (f64, f64, f64)) {
    let pos = cell_center(h, w, d, gh, gw, gd);
    let vel = (gravity.0 * birth_velocity_scale, gravity.1 * birth_velocity_scale, gravity.2 * birth_velocity_scale);
    (pos, vel)
}

/// Advance each dark-matter particle one step in the current gravity field
/// (CIC gather), then wrap periodically. No drag, no coupling to baryon density
/// -> collisionless, multi-streaming allowed.
pub fn push_dimple_particles(particles: &mut [StructureParticle], grid: &Vec<Vec<Vec<Cell>>>, gh: usize, gw: usize, gd: usize, dt: f64) {
    for p in particles.iter_mut() {
        let (i0, i1, fx) = cic_axis(p.position_x, gh);
        let (j0, j1, fy) = cic_axis(p.position_y, gw);
        let (k0, k1, fz) = cic_axis(p.position_z, gd);
        let (gx, gy, gz) = gather_gravity_cic(grid, i0, i1, fx, j0, j1, fy, k0, k1, fz);
        p.velocity_x += gx * dt;
        p.velocity_y += gy * dt;
        p.velocity_z += gz * dt;
        for v in [&mut p.velocity_x, &mut p.velocity_y, &mut p.velocity_z] {
            if !v.is_finite() {
                *v = 0.0;
            }
        }
        p.position_x = wrap_unit(p.position_x + p.velocity_x * dt);
        p.position_y = wrap_unit(p.position_y + p.velocity_y * dt);
        p.position_z = wrap_unit(p.position_z + p.velocity_z * dt);
    }
}

/// Rebuild the grid `rip_dimple` field as the CIC projection of the particle
/// masses. The grid field is a pure projection in particle mode, so it is zeroed
/// first. CIC conserves mass exactly, so total rip_dimple == total particle mass.
/// Deposit is serial (parallel writers would race on shared cells); the zeroing
/// is parallel. Particle counts are modest; revisit with per-thread partials if
/// this becomes hot.
pub fn scatter_dimple_to_grid(particles: &[StructureParticle], grid: &mut Vec<Vec<Vec<Cell>>>, _gh: usize, _gw: usize, _gd: usize) {
    grid.par_iter_mut().for_each(|plane| {
        plane.iter_mut().for_each(|row| {
            row.iter_mut().for_each(|cell| {
                cell.rip_dimple = 0.0;
            });
        });
    });
    let (gh, gw, gd) = (grid.len(), grid[0].len(), grid[0][0].len());
    for p in particles.iter() {
        if p.mass <= 0.0 {
            continue;
        }
        let (i0, i1, fx) = cic_axis(p.position_x, gh);
        let (j0, j1, fy) = cic_axis(p.position_y, gw);
        let (k0, k1, fz) = cic_axis(p.position_z, gd);
        let m = p.mass;
        grid[i0][j0][k0].rip_dimple += m * (1.0 - fx) * (1.0 - fy) * (1.0 - fz);
        grid[i1][j0][k0].rip_dimple += m * fx * (1.0 - fy) * (1.0 - fz);
        grid[i0][j1][k0].rip_dimple += m * (1.0 - fx) * fy * (1.0 - fz);
        grid[i0][j0][k1].rip_dimple += m * (1.0 - fx) * (1.0 - fy) * fz;
        grid[i1][j1][k0].rip_dimple += m * fx * fy * (1.0 - fz);
        grid[i1][j0][k1].rip_dimple += m * fx * (1.0 - fy) * fz;
        grid[i0][j1][k1].rip_dimple += m * (1.0 - fx) * fy * fz;
        grid[i1][j1][k1].rip_dimple += m * fx * fy * fz;
    }
}

/// Expansion dilution applied to particle mass — the bounded-total sink in
/// particle mode (the grid projection is rebuilt from scatter, so diluting it
/// would desync it). Same (a_prev/a_now)^p factor as the Tier 1 grid dilution.
pub fn dilute_dimple_particles(particles: &mut [StructureParticle], dilution: f64) {
    for p in particles.iter_mut() {
        p.mass *= dilution;
    }
}

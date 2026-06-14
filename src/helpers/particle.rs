use crate::database::entities::structure_particle::StructureParticle;
use crate::helpers::particle::f64::consts::PI;
use rand::Rng;
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

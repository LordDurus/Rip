use crate::AppSettings;
use crate::DbProvider;
use crate::LogLevel;
use crate::create_data::f64::consts::PI;
use crate::database::entities::cell::Cell;
use crate::database::entities::structure_particle::StructureParticle;
use indicatif::ProgressBar;
use rand::Rng;
use rand::rngs::ThreadRng;
use rayon::prelude::*;
use std::f64;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

fn initialize_particles(
    rng: &mut ThreadRng,
    positions: &mut Vec<(f64, f64, f64)>,
    velocities: &mut Vec<(f64, f64, f64)>,
) {
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
fn compute_scale_factor(
    scale: f64,
    timestep: usize,
    settings: &AppSettings,
    step_duration: f64,
) -> f64 {
    let ramp = 1.0 - f64::exp(-settings.rip_decay_rate * timestep as f64);
    let decay = f64::exp(-settings.rip_evaporation_rate * timestep as f64);
    let healing = 1.0; // placeholder if I later want global curvature/density influence
    let global_rip_strength = settings.rip_initial * ramp * decay * healing;

    let expansion_factor = global_rip_strength.sqrt() * step_duration;
    if expansion_factor > 0.05 {
        return scale * f64::exp(expansion_factor);
    }
    return scale;
}

#[inline(always)]
fn apply_gravity_to_particle(
    particle: &mut StructureParticle,
    gravity: (f64, f64, f64),
    timestep: f64,
) {
    // apply gravity to velocity
    particle.velocity_x += gravity.0 * timestep;
    particle.velocity_y += gravity.1 * timestep;
    particle.velocity_z += gravity.2 * timestep;

    for coord in [
        &mut particle.velocity_x,
        &mut particle.velocity_y,
        &mut particle.velocity_z,
    ] {
        if !coord.is_finite() {
            *coord = 0.0;
        }
    }

    // update position
    particle.position_x += particle.velocity_x * timestep;
    particle.position_y += particle.velocity_y * timestep;
    particle.position_z += particle.velocity_z * timestep;
}

#[inline(always)]
pub fn map_particle_to_cell(
    x: f64,
    y: f64,
    z: f64,
    grid_width: usize,
    grid_height: usize,
    grid_depth: usize,
) -> Option<(usize, usize, usize)> {
    if !(x >= -1.0 && x <= 1.0 && y >= -1.0 && y <= 1.0 && z >= -1.0 && z <= 1.0) {
        return None; // out of bounds
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

fn seed_initial_curvature(
    grid: &mut Vec<Vec<Vec<Cell>>>,
    settings: &AppSettings,
    db: &mut dyn DbProvider,
) {
    let progress_bar: ProgressBar = ProgressBar::new(
        (settings.inf_grid_height * settings.inf_grid_width * settings.inf_grid_depth) as u64,
    );

    let mut current_id: i64 = 1;
    let mut rng = rand::thread_rng();
    let mut id_lookup = vec![
        vec![vec![-1i64; settings.inf_grid_depth]; settings.inf_grid_height];
        settings.inf_grid_width
    ];

    // phase 2: assign curvature and neighbors
    for height in 0..settings.inf_grid_height {
        for width in 0..settings.inf_grid_width {
            for depth in 0..settings.inf_grid_depth {
                let cell = &mut grid[height][width][depth];
                progress_bar.inc(1);
                id_lookup[height][width][depth] = current_id;
                current_id += 1;
                cell.layer = depth;
                cell.position = db.get_or_insert_cell_position(height, width);
                cell.curvature = rng.gen_range(0.0..0.1);

                grid[height][width][depth].curvature *= 1.0 + (height as f64);
            }
        }
    }
    progress_bar.finish_with_message("Seeding simulation complete.");
}

#[inline(always)]
fn compute_cell_rip_strength(timestep: usize, cell: &Cell, settings: &AppSettings) -> f64 {
    let ramp = 1.0 - f64::exp(-settings.rip_decay_rate * timestep as f64);
    let healing = 1.0 / (1.0 + cell.curvature + cell.matter_density);
    let decay = f64::exp(-settings.rip_evaporation_rate * timestep as f64);
    let global_rip_strength = settings.rip_initial * ramp * decay * healing;
    let modifier = 1.0
        + settings.rip_curvature_weight * cell.curvature
        + settings.rip_density_weight * cell.matter_density;

    return (global_rip_strength * modifier).clamp(settings.rip_minimum_strength, 1.0e6);
}

fn set_as_black_hole(cell: &mut Cell, next_black_hole_id: &Arc<Mutex<u64>>) {
    cell.is_black_hole = true;
    let mut id = next_black_hole_id.lock().unwrap();
    cell.black_hole_id = Some(*id);
    *id += 1;
    drop(id);

    // mark as singularity; normal density rules do not apply
    cell.matter_density = f64::MAX;
    cell.dimple_strength = f64::MAX;
}

pub fn run(
    app_settings: &AppSettings,
    db: &mut dyn DbProvider,
) -> Result<(), Box<dyn std::error::Error>> {
    const STEP_DURATION: f64 = 0.01;
    const MAX_DIMPLE_NON_BH: f64 = 1e4; // adjust based on simulation scale

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();

    ctrlc::set_handler(move || {
        println!("\nCtrl+C detected — exiting simulation...");
        r.store(false, Ordering::SeqCst);
    })?;

    let mut grid =
        vec![
            vec![vec![Cell::new(); app_settings.inf_grid_depth]; app_settings.inf_grid_width];
            app_settings.inf_grid_height
        ];

    seed_initial_curvature(&mut grid, &app_settings, db);

    let num_particles = app_settings.structure_num_particles;
    let mut rng = rand::thread_rng();
    let mut positions = vec![(0.0, 0.0, 0.0); num_particles];
    let mut velocities = vec![(0.0, 0.0, 0.0); num_particles];
    initialize_particles(&mut rng, &mut positions, &mut velocities);

    let mut particles: Vec<StructureParticle> = positions
        .iter()
        .zip(velocities.iter())
        .map(|(&(x, y, z), &(vx, vy, vz))| StructureParticle {
            time: 0.0,
            rip_strength: 0.0,
            scale_factor: 1.0,
            position_x: x,
            position_y: y,
            position_z: z,
            velocity_x: vx,
            velocity_y: vy,
            velocity_z: vz,
        })
        .collect();

    let raw_density = Arc::new(Mutex::new(vec![
        vec![
            vec![0.0; app_settings.inf_grid_depth];
            app_settings.inf_grid_width
        ];
        app_settings.inf_grid_height
    ]));

    let next_black_hole_id: Arc<Mutex<u64>> = Arc::new(Mutex::new(1));
    let mut scale_factor = 1.0;

    let progress_bar = Arc::new(ProgressBar::new(app_settings.num_timesteps as u64));
    // let decay_rate = settings.rip_decay_rate;
    println!("Starting Timesteps...");

    for timestep in 0..app_settings.num_timesteps {
        if !running.load(Ordering::SeqCst) {
            println!("Stopped at timestep {}", timestep);
            break;
        }

        progress_bar.inc(1);
        /*
        -- Old
        let ramp = 1.0 - f64::exp(-settings.rip_decay_rate * timestep as f64);
        let global_rip_strength = settings.rip_initial * ramp;
        scale_factor *= f64::exp(global_rip_strength.sqrt() * STEP_DURATION);
        */

        scale_factor = compute_scale_factor(scale_factor, timestep, &app_settings, STEP_DURATION);

        grid.par_iter_mut().enumerate().for_each(|(height, col)| {
            let running = Arc::clone(&running);
            col.iter_mut().enumerate().for_each(|(width, row)| {
                row.iter_mut().enumerate().for_each(|(depth, cell)| {
                    if !running.load(Ordering::SeqCst) {
                        println!("Stopped at timestep {}", timestep);
                        return;
                    }
                    cell.timestep = timestep;
                    cell.apply_gravity_interaction();

                    cell.rip_strength = compute_cell_rip_strength(timestep, cell, &app_settings);

                    cell.scale_factor = scale_factor;

                    if !cell.is_black_hole
                        && cell.curvature > app_settings.curvature_threshold
                        && cell.matter_density > app_settings.collapse_density_threshold
                    {
                        set_as_black_hole(cell, &next_black_hole_id);
                    }

                    cell.mass = cell.matter_density * cell.volume;

                    let mut raw = raw_density.lock().unwrap();
                    raw[height][width][depth] = cell.matter_density;
                    drop(raw); // unlock the mutex manually before continuing

                    cell.compute_gravity_from_density(
                        height,
                        width,
                        depth,
                        &raw_density.lock().unwrap(),
                        app_settings.inf_grid_width,
                        app_settings.inf_grid_height,
                        app_settings.inf_grid_depth,
                    );
                });
            });
        });

        for particle in &mut particles {
            if let Some((col_idx, row_idx, depth_idx)) = map_particle_to_cell(
                particle.position_x,
                particle.position_y,
                particle.position_z,
                app_settings.inf_grid_height,
                app_settings.inf_grid_width,
                app_settings.inf_grid_depth,
            ) {
                if let Some(col) = grid.get_mut(col_idx) {
                    if let Some(row) = col.get_mut(row_idx) {
                        if let Some(cell) = row.get_mut(depth_idx) {
                            let gravity = (cell.gravity_x, cell.gravity_y, cell.gravity_z);
                            apply_gravity_to_particle(particle, gravity, STEP_DURATION);

                            let gravity_magnitude = (cell.gravity_x.powi(2)
                                + cell.gravity_y.powi(2)
                                + cell.gravity_z.powi(2))
                            .sqrt();

                            if cell.is_black_hole || gravity_magnitude > MAX_DIMPLE_NON_BH {
                                set_as_black_hole(cell, &next_black_hole_id);
                                if !cell.is_black_hole {
                                    cell.is_rip_induced = true;
                                }
                            } else {
                                cell.dimple_strength = gravity_magnitude.min(MAX_DIMPLE_NON_BH);
                            }
                        }
                    }
                }
            }
        }

        if let Err(err) = db.insert_particle_batch(&particles) {
            let message = format!("failed to insert particle batch: {err}");
            let _ = db.log_message("structure", LogLevel::Error, &message);
            return Err(err.into());
        }

        db.save_all_cells(&mut grid).expect("Error saving cells");
        db.record_rip_field_summary(timestep, 100.0, &grid)
            .expect("failed to record rip field summary");
    }
    let count = grid
        .iter()
        .flat_map(|col| col.iter())
        .flat_map(|row| row.iter())
        .filter(|cell| cell.is_black_hole)
        .count();

    progress_bar.finish_with_message("Inflation simulation complete.");
    dbg!("Black holes created: {}", count);
    return Ok(());
}

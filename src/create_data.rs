use crate::AppSettings;
use crate::create_data::f64::consts::PI;
use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use crate::enums::rip_decay_mechanism::RipDecayMechanism;
use crate::gravity::compute_gravity_fft;
use crate::helpers::rip::compute_cell_rip_strength;
use crate::initial_geometry::InitialGeometry;
use crate::populate_grid::populate_grid;
use colored::Colorize;
use crossterm::event::{self, Event, KeyCode, KeyEvent};
use crossterm::terminal::{disable_raw_mode, enable_raw_mode};
use indicatif::ProgressBar;
use rand::Rng;
use rayon::prelude::*;
use std::f64;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

fn initialize_particles(positions: &mut Vec<(f64, f64, f64)>, velocities: &mut Vec<(f64, f64, f64)>) {
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
fn apply_gravity_to_particle(particle: &mut StructureParticle, gravity: (f64, f64, f64), timestep: f64) {
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

fn seed_initial_curvature(grid: &mut Vec<Vec<Vec<Cell>>>, settings: &AppSettings, db: &mut dyn DbProvider) {
    let progress_bar: ProgressBar = ProgressBar::new((settings.inf_grid_height * settings.inf_grid_width * settings.inf_grid_depth) as u64);

    let mut rng = rand::thread_rng();

    for height in 0..settings.inf_grid_height {
        for width in 0..settings.inf_grid_width {
            for depth in 0..settings.inf_grid_depth {
                let cell = &mut grid[height][width][depth];
                progress_bar.inc(1);
                cell.layer = depth;
                cell.position = db.get_or_insert_cell_position(width, height);
                cell.curvature = rng.gen_range(0.0..0.1);
            }
        }
    }
    progress_bar.finish_with_message("Seeding simulation complete.");
}

fn set_as_black_hole(cell: &mut Cell, next_black_hole_id: &Arc<Mutex<u64>>) {
    cell.is_black_hole = true;
    let mut id = next_black_hole_id.lock().unwrap();
    cell.black_hole_id = Some(*id);
    *id += 1;
    drop(id);

    cell.matter_density = 1.0e30;
    cell.dimple_strength = 1.0e30;
}

struct RawModeGuard;
impl Drop for RawModeGuard {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
    }
}

pub fn run(app_settings: &AppSettings, db: &mut dyn DbProvider) -> Result<(), Box<dyn std::error::Error>> {
    const STEP_DURATION: f64 = 0.01;
    const MAX_DIMPLE_NON_BH: f64 = 1e4;
    const DIRTY_GRAVITY_THRESHOLD: f64 = 1e-12;
    const MODULE: &str = "create_data->run";

    let _raw = RawModeGuard; // disable_raw_mode called automatically when this drops
    enable_raw_mode()?;

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();

    ctrlc::set_handler(move || {
        println!("\nCtrl+C detected — exiting simulation...");
        r.store(false, Ordering::SeqCst);
    })?;

    let geometry = InitialGeometry::from_settings(app_settings);
    let decay_mechanism = RipDecayMechanism::from_settings(app_settings);

    for run_index in 0..app_settings.num_runs {
        if !running.load(Ordering::SeqCst) {
            println!("Stopped before run {}", run_index);
            break;
        }

        let seed: u64 = rand::thread_rng().r#gen();
        let run = db.start_run(seed, Some("baseline")).expect("Failed to start run");
        println!(
            "{} {}{}{} {}{}{}",
            "Starting run".white(),
            (run_index + 1),
            " of ".white(),
            app_settings.num_runs,
            "(run_id=".white(),
            run.run_id,
            ")".white()
        );

        let mut grid = vec![vec![vec![Cell::new(); app_settings.inf_grid_depth]; app_settings.inf_grid_width]; app_settings.inf_grid_height];

        seed_initial_curvature(&mut grid, &app_settings, db);

        let num_particles = app_settings.structure_num_particles;
        let mut positions = vec![(0.0, 0.0, 0.0); num_particles];
        let mut velocities = vec![(0.0, 0.0, 0.0); num_particles];
        initialize_particles(&mut positions, &mut velocities);

        if let Err(err) = populate_grid(&geometry, &mut grid, db) {
            let message = format!("failed to populate initial geometry: {err}");
            _ = db.log_message(run.run_id, MODULE, LogLevel::Error, &message);
            _ = db.fail_run(run.run_id, message);
            return Err(err.into());
        }

        // Compute initial total matter as baseline for expansion calculation
        let mut previous_total_matter: f64 = grid
            .iter()
            .flat_map(|col| col.iter())
            .flat_map(|row| row.iter())
            .filter(|cell| !cell.is_black_hole)
            .map(|cell| cell.matter_density)
            .sum();

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
            vec![vec![0.0; app_settings.inf_grid_depth]; app_settings.inf_grid_width];
            app_settings.inf_grid_height
        ]));
        let next_black_hole_id: Arc<Mutex<u64>> = Arc::new(Mutex::new(1));
        let mut scale_factor = 1.0;

        let progress_bar = Arc::new(ProgressBar::new(app_settings.num_timesteps as u64));
        println!("Starting Timesteps...");

        for timestep in 0..app_settings.num_timesteps {
            if !running.load(Ordering::SeqCst) {
                println!("Stopped at timestep {}", timestep);
                break;
            }

            progress_bar.inc(1);

            if event::poll(Duration::from_millis(0)).unwrap_or(false) {
                if let Ok(event) = event::read() {
                    match event {
                        Event::Key(KeyEvent { code: KeyCode::Pause, .. }) => {
                            println!("\nPaused at timestep {}. Continue or Quit? (c/q)", timestep);
                            loop {
                                let mut input = String::new();
                                std::io::stdin().read_line(&mut input).unwrap();
                                match input.trim().to_lowercase().as_str() {
                                    "c" => break,
                                    "q" => {
                                        println!("Quitting at timestep {}", timestep);
                                        _ = db.fail_run(run.run_id, "User quit".to_string());
                                        running.store(false, Ordering::SeqCst);
                                        break;
                                    }
                                    _ => println!("Please enter c to continue or q to quit:"),
                                }
                            }
                        }
                        Event::Key(KeyEvent { code: KeyCode::Esc, .. }) => {} // silently continue
                        _ => {}
                    }
                }
            }

            // Break out of timestep loop if user quit
            if !running.load(Ordering::SeqCst) {
                break;
            }

            grid.par_iter_mut().enumerate().for_each(|(height, col)| {
                let running = Arc::clone(&running);
                col.iter_mut().enumerate().for_each(|(width, row)| {
                    row.iter_mut().enumerate().for_each(|(depth, cell)| {
                        if !running.load(Ordering::SeqCst) {
                            return;
                        }

                        cell.timestep = timestep;
                        cell.scale_factor = scale_factor;
                        cell.rip_strength = compute_cell_rip_strength(timestep, cell, &app_settings, &decay_mechanism, STEP_DURATION);

                        // Black hole formation — set_as_black_hole marks dirty internally
                        if !cell.is_black_hole {
                            if cell.curvature > app_settings.curvature_threshold && cell.matter_density > app_settings.collapse_density_threshold {
                                set_as_black_hole(cell, &next_black_hole_id);
                                cell.is_rip_induced = false;
                            } else if cell.rip_strength > app_settings.rip_induced_threshold {
                                set_as_black_hole(cell, &next_black_hole_id);
                                cell.is_rip_induced = true;
                            }
                        }

                        cell.mass = cell.matter_density * cell.volume;

                        let mut raw = raw_density.lock().unwrap();
                        raw[height][width][depth] = cell.matter_density;
                        drop(raw);
                    });
                });
            });

            // Compute gravity for all cells at once via FFT
            let density_snapshot = {
                let raw = raw_density.lock().unwrap();
                raw.clone()
            };

            let (gx, gy, gz) = compute_gravity_fft(
                &density_snapshot,
                app_settings.gravity,
                app_settings.inf_grid_height,
                app_settings.inf_grid_width,
                app_settings.inf_grid_depth,
            );

            // Write gravity back — only mark dirty if vectors changed meaningfully
            grid.par_iter_mut().enumerate().for_each(|(h, col)| {
                col.iter_mut().enumerate().for_each(|(w, row)| {
                    row.iter_mut().enumerate().for_each(|(d, cell)| {
                        cell.gravity_x = gx[h][w][d];
                        cell.gravity_y = gy[h][w][d];
                        cell.gravity_z = gz[h][w][d];
                    });
                });
            });

            // Accretion and rip drain — compete to grow or reduce matter density
            grid.par_iter_mut().for_each(|col| {
                col.iter_mut().for_each(|row| {
                    row.iter_mut().for_each(|cell| {
                        if !cell.is_black_hole {
                            let gravity_magnitude = (cell.gravity_x.powi(2) + cell.gravity_y.powi(2) + cell.gravity_z.powi(2)).sqrt();
                            let accretion = (app_settings.accretion_rate * gravity_magnitude * cell.matter_density).min(cell.matter_density * 0.01);
                            let drain = app_settings.rip_drain_rate * cell.rip_strength * cell.matter_density;
                            cell.matter_density = (cell.matter_density + accretion - drain).max(0.0);
                        }
                    });
                });
            });

            // Compute current total matter and update scale factor
            // Matter loss drives expansion; matter gain causes slight contraction.
            // Scale factor has a floor of 1.0 — the universe cannot un-exist.
            let current_total_matter: f64 = grid
                .iter()
                .flat_map(|col| col.iter())
                .flat_map(|row| row.iter())
                .filter(|cell| !cell.is_black_hole)
                .map(|cell| cell.matter_density)
                .sum();

            let matter_delta = previous_total_matter - current_total_matter;
            scale_factor = (scale_factor * f64::exp(matter_delta * app_settings.matter_expansion_rate)).max(1.0);
            previous_total_matter = current_total_matter;

            // Apply gravity to particles and update dimple strength
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

                                let gravity_magnitude = (cell.gravity_x.powi(2) + cell.gravity_y.powi(2) + cell.gravity_z.powi(2)).sqrt();

                                if cell.is_black_hole || gravity_magnitude > MAX_DIMPLE_NON_BH {
                                    let already_bh = cell.is_black_hole;
                                    set_as_black_hole(cell, &next_black_hole_id);
                                    if !already_bh {
                                        cell.is_rip_induced = true;
                                    }
                                } else {
                                    let new_dimple = gravity_magnitude.min(MAX_DIMPLE_NON_BH);
                                    if (new_dimple - cell.dimple_strength).abs() > DIRTY_GRAVITY_THRESHOLD {
                                        cell.dimple_strength = new_dimple;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if let Err(err) = db.insert_particle_batch(&particles) {
                let message = format!("failed to insert particle batch: {err}");
                _ = db.log_message(run.run_id, MODULE, LogLevel::Error, &message);
                _ = db.fail_run(run.run_id, message);
                return Err(err.into());
            }

            db.save_all_cells(run.run_id, &mut grid).expect("Error saving cells");
            db.record_timestep_summary(timestep, 100.0, &grid, run.run_id).expect("failed to record rip field summary");
        }

        let count = grid.iter().flat_map(|col| col.iter()).flat_map(|row| row.iter()).filter(|cell| cell.is_black_hole).count();

        progress_bar.finish_with_message("Inflation simulation complete.");
        println!("Run {} complete. Black holes created: {}", run_index + 1, count);

        if let Err(err) = db.complete_run(run.run_id) {
            let message = format!("failed to complete run: {err}");
            let _ = db.log_message(run.run_id, MODULE, LogLevel::Error, &message);
        }
    }

    return Ok(());
}

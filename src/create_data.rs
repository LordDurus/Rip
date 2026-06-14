use crate::AppSettings;
use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use crate::enums::rip_decay_mechanism::RipDecayMechanism;
use crate::enums::smbh_connection_mode::SmbhConnectionMode;
use crate::gravity::compute_gravity_fft;
use crate::helpers::black_hole::{revert_black_hole, set_as_black_hole};
use crate::helpers::grid::{populate_grid, seed_initial_curvature};
use crate::helpers::particle::{apply_gravity_to_particle, initialize_particles, map_particle_to_cell};
use crate::helpers::rip::compute_cell_rip_strength;
use crate::helpers::transport::apply_matter_transport;
use crate::initial_geometry::InitialGeometry;
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

        // Built once: which mode assigns per-SMBH parent-connection strength.
        let smbh_connection_mode = SmbhConnectionMode::from_settings(&app_settings);
        let smbh_connection_alpha = app_settings.smbh_connection_alpha;

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
                            // SMBH formation — rare high-curvature seeds with early-time bias.
                            // Checked first: an SMBH seed should not be "claimed" by the
                            // ordinary collapse path before it gets the chance to form.
                            // Probability decays exponentially with timestep so early
                            // formation is favored (the JWST overmassive-early-BH regime).
                            let smbh_probability = app_settings.smbh_formation_probability * f64::exp(-(timestep as f64) / app_settings.smbh_early_bias);
                            let mut rng = rand::thread_rng();
                            if cell.curvature > app_settings.smbh_curvature_threshold && rng.gen_range(0.0..1.0) < smbh_probability {
                                set_as_black_hole(cell, &next_black_hole_id);
                                cell.is_supermassive = true;
                                cell.is_rip_induced = false;
                                // Form already-massive: rapid early feeding from the host.
                                // Ensures the SMBH dominates local gravity and grows from there.
                                cell.matter_density = cell.matter_density.max(app_settings.smbh_initial_density);
                                // Assign this SMBH's parent-connection feed rate. Heavy-tailed:
                                // u^alpha crushes most draws toward 0 (stalls) with a rare strong
                                // tail (runaway). Mode chooses whether the scale is tied to the
                                // depth of the curvature well or drawn independently.
                                let u: f64 = rng.gen_range(0.0..1.0);
                                let heavy_tail = u.powf(smbh_connection_alpha);
                                cell.smbh_connection_strength = match &smbh_connection_mode {
                                    SmbhConnectionMode::TiedToCurvature { rate } => rate * (cell.curvature - app_settings.smbh_curvature_threshold) * heavy_tail,
                                    SmbhConnectionMode::IndependentDraw { rate } => rate * heavy_tail,
                                };
                            } else if cell.curvature > app_settings.curvature_threshold && cell.matter_density > app_settings.collapse_density_threshold {
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
                        if cell.is_black_hole {
                            if cell.is_supermassive {
                                // Active feeding from the parent geometry at this SMBH's own
                                // connection strength (heavy-tailed, assigned at formation).
                                // Most SMBHs have near-zero strength and stall near drain-balance;
                                // a rare few with strong connections run away to overmassive scale.
                                cell.matter_density += cell.smbh_connection_strength * cell.matter_density;
                                // still subject to drain; net growth only when connection > drain
                                cell.matter_density = (cell.matter_density - app_settings.bh_drain_rate * cell.matter_density).max(0.0);
                                // no reversal check — persistence is a *consequence* of net positive growth,
                                // not an exemption
                            } else {
                                // normal BH: drain only (the clock), then revert below threshold
                                // let drain = app_settings.rip_drain_rate * cell.rip_strength * cell.matter_density;
                                // cell.matter_density = (cell.matter_density - drain).max(0.0);
                                cell.matter_density = (cell.matter_density - app_settings.bh_drain_rate * cell.matter_density).max(0.0);
                                let below = if cell.is_rip_induced {
                                    cell.rip_strength < app_settings.rip_induced_threshold * 0.5
                                } else {
                                    cell.matter_density < app_settings.collapse_density_threshold * 0.5
                                };
                                if below {
                                    revert_black_hole(cell);
                                }
                            }
                        } else {
                            let drain = app_settings.rip_drain_rate * cell.rip_strength * cell.matter_density;
                            cell.matter_density = (cell.matter_density - drain).max(0.0);
                        }
                    });
                });
            });
            apply_matter_transport(&mut grid, &app_settings, STEP_DURATION);

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

            //  the following code should be faithful to exp(k·(M₀−Mₜ))
            scale_factor = scale_factor * f64::exp(matter_delta * app_settings.matter_expansion_rate);
            if scale_factor.is_nan() || scale_factor.is_infinite() {
                panic!("scale_factor non-finite at timestep {}: {} (matter_delta {})", timestep, scale_factor, matter_delta);
            }

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
            db.record_timestep_summary(timestep, 100.0, &grid, run.run_id, scale_factor, current_total_matter)
                .expect("failed to record rip field summary");
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

use crate::AppSetting;
use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use crate::enums::rip_decay_mechanism::RipDecayMechanism;
use crate::enums::smbh_connection_mode::SmbhConnectionMode;
use crate::galaxy::{Galaxy, apply_smbh_competition, build_membership, find_galaxies, persist_galaxies};
use crate::gravity::compute_gravity_fft;
use crate::helpers::black_hole::{revert_black_hole, set_as_black_hole};
use crate::helpers::grid::{populate_grid, seed_initial_curvature};
use crate::helpers::particle::{apply_gravity_to_particle, initialize_particles, map_particle_to_cell};
use crate::helpers::rip::compute_cell_rip_strength;
use crate::helpers::transport::{apply_dimple_transport, apply_matter_transport};
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

pub fn run(app_settings: &AppSetting, db: &mut dyn DbProvider) -> Result<(), Box<dyn std::error::Error>> {
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

        let mut galaxies = seed_initial_curvature(&mut grid, &app_settings, db);
        Galaxy::assign_run_id(&mut galaxies, run.run_id);
        // Galaxies are found dynamically each post-inflation timestep, not seeded.
        // `galaxies` starts empty (seed_initial_curvature returns an empty Vec).
        // prev_membership carries cell->galaxy_id from the prior step for identity
        // matching. New galaxy ids come from the DB (autoincrement), assigned in
        // persist_galaxies — there is no in-memory counter. prev_galaxy_ids tracks
        // which ids existed last step so persist_galaxies can deactivate any that
        // vanish (merged/dissolved).
        let mut prev_membership: std::collections::HashMap<(usize, usize, usize), i64> = std::collections::HashMap::new();
        let mut prev_galaxy_ids: std::collections::HashSet<i64> = std::collections::HashSet::new();

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

        // Galaxy overdensity seeding removed: galaxies emerge from the density
        // field via friends-of-friends after inflation, not from init-time stamps.

        // Compute initial total matter as baseline for expansion calculation
        // Start "maximally unstable" so star formation is blocked until the first
        // real matter_delta proves the universe has stabilised (inflation ending).
        // Using 0.0 here would wrongly read as "stable" on timestep 0.
        let mut previous_matter_delta: f64 = f64::INFINITY;
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
                run_id: run.run_id,
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

            // ── Galaxy finding pass ──
            // Galaxies are found fresh from the density field each timestep via
            // friends-of-friends, but only AFTER inflation settles — during the
            // violent early epoch matter can't bind into galaxies. We reuse the
            // star-formation stability signal: the previous step's matter_delta
            // below the threshold means the universe has calmed enough.
            //
            // SMBH formation is NOT gated here — it's exogenous (parent feed) and
            // handled in the cell update regardless of galaxy state.
            //
            // Runs BEFORE the cell update so the cell pass sees current galaxy tags.
            let galaxies_allowed = previous_matter_delta.abs() < app_settings.star_formation_max_matter_delta;
            if galaxies_allowed {
                galaxies = find_galaxies(&mut grid, &prev_membership, &app_settings, timestep, run.run_id);
                apply_smbh_competition(&galaxies, &mut grid, &app_settings);
                // Persist BEFORE build_membership: this swaps newborn sentinel ids
                // for real DB rowids and re-tags the grid, so the membership map
                // carries real positive ids forward for next step's identity match.
                if let Err(err) = persist_galaxies(db, &mut galaxies, &mut grid, &prev_galaxy_ids, timestep) {
                    let message = format!("Failed to persist galaxies at timestep {timestep}: {err}");
                    _ = db.log_message(run.run_id, MODULE, LogLevel::Error, &message);
                    _ = db.fail_run(run.run_id, message.clone());
                    return Err(message.into());
                }
                prev_membership = build_membership(&grid);
                prev_galaxy_ids = galaxies.iter().map(|g| g.galaxy_id).collect();
            }

            // Use previous timestep's matter_delta to gate star formation.
            // matter_delta for the current timestep isn't computed until after
            // the cell update — using the prior step's value is correct:
            // we're asking "was the universe stable enough last step for stars to form?"
            let matter_delta_snapshot = previous_matter_delta;

            grid.par_iter_mut().enumerate().for_each(|(height, col)| {
                let running = Arc::clone(&running);
                let matter_delta = matter_delta_snapshot;
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
                            // Capture the matter about to leave spacetime. Any of the
                            // rip paths below removes this cell's matter into a child
                            // geometry; whichever fires, the dark-matter dimple deposit
                            // is proportional to what left. No special cases — every
                            // matter-removal site leaves a fossil dimple.
                            let matter_before_rip = cell.matter_density;
                            let was_black_hole = cell.is_black_hole;

                            // SMBH formation — rare high-curvature seeds with early-time bias.
                            // Checked first: an SMBH seed should not be "claimed" by the
                            // ordinary collapse path before it gets the chance to form.
                            // Probability decays exponentially with timestep so early
                            // formation is favored (the JWST overmassive-early-BH regime).
                            let smbh_probability = app_settings.smbh_formation_probability * f64::exp(-(timestep as f64) / app_settings.smbh_early_bias);
                            let mut rng = rand::thread_rng();
                            // No galaxy gating: SMBHs are exogenous — seeded by a
                            // feeding black hole in the parent universe, which we do
                            // not model and cannot time. They may form anywhere, any
                            // time (including during/before inflation). Galaxies later
                            // condense around the wells these seeds leave behind.
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

                            // Dark-matter dimple: if a rip fired this iteration (the cell
                            // became a black hole), deposit a persistent fossil dimple
                            // proportional to the matter that just left spacetime. The
                            // dimple gravitates (sources the Poisson solve) but is NOT
                            // baryonic matter and is excluded from total_matter / the
                            // inflation calc. Decoupled from mass — the matter still fully
                            // leaves and drives expansion; the dimple is created in
                            // addition (the intentional GR break). Accumulates across
                            // repeated rips at a site; bounded by expansion dilution.
                            if cell.is_black_hole && !was_black_hole {
                                cell.rip_dimple += app_settings.dimple_retention * matter_before_rip;
                            }
                        }

                        // Star formation/extinction — non-BH cells only.
                        // BH checks above take priority; a cell dense enough to collapse
                        // never reaches this branch. Hysteresis between formation and
                        // extinction thresholds prevents rapid flickering.
                        if !cell.is_black_hole {
                            // Star formation gated on matter_delta: when matter loss rate
                            // exceeds the threshold the universe is too hot/chaotic for
                            // gravitational collapse to produce stars (analog of pre-recombination).
                            // Extinction is always allowed — stars can die regardless of epoch.
                            let star_formation_allowed = matter_delta.abs() < app_settings.star_formation_max_matter_delta;
                            if !cell.is_star && star_formation_allowed && cell.matter_density >= app_settings.star_formation_threshold && cell.matter_density < app_settings.collapse_density_threshold
                            {
                                cell.is_star = true;
                            } else if cell.is_star && cell.matter_density < app_settings.star_extinction_threshold {
                                cell.is_star = false;
                            }
                        }

                        cell.mass = cell.matter_density * cell.volume;

                        let mut raw = raw_density.lock().unwrap();
                        // Dark-matter dimple sources gravity alongside baryonic matter:
                        // the persistent fossil curvature left by past rips gravitates
                        // through the same Poisson solve, but is NOT baryonic matter and
                        // is deliberately excluded from total_matter / the inflation calc.
                        raw[height][width][depth] = cell.matter_density + cell.rip_dimple;
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
                            // Cells inside a galaxy get partial drain protection —
                            // galaxy structure resists rip-driven matter loss.
                            // galaxy_id > 0 when find_galaxies tagged this cell
                            // as a galaxy member this timestep (0 = no galaxy).
                            let drain_factor = if cell.galaxy_id > 0 { 0.1 } else { 1.0 };
                            let drain = app_settings.rip_drain_rate * cell.rip_strength * cell.matter_density * drain_factor;
                            cell.matter_density = (cell.matter_density - drain).max(0.0);

                            // Star burn: active stars slowly consume matter each timestep.
                            // Burned matter stays in the cell as diffuse gas — density drops
                            // but matter does not leave the grid, so galaxy budget is intact.
                            if cell.is_star {
                                cell.matter_density *= 1.0 - app_settings.star_burn_rate;
                            }
                        }
                    });
                });
            });
            apply_matter_transport(&mut grid, &app_settings, STEP_DURATION);
            // Tier 1: collisionless dimple advection. The dark-matter dimple falls
            // down the total gravity gradient and clusters into wells, carving the
            // density contrast that lensing needs. Conservative (redistributes,
            // does not create/destroy); dilution remains the sole sink, so the
            // validated boundedness is intact. dimple_transport_rate = 0 disables.
            apply_dimple_transport(&mut grid, &app_settings, STEP_DURATION);

            // Process mergers — smaller galaxy absorbed into larger.

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
            let scale_factor_prev = scale_factor;
            scale_factor = scale_factor * f64::exp(matter_delta * app_settings.matter_expansion_rate);
            if scale_factor.is_nan() || scale_factor.is_infinite() {
                panic!("scale_factor non-finite at timestep {}: {} (matter_delta {})", timestep, scale_factor, matter_delta);
            }

            previous_total_matter = current_total_matter;
            previous_matter_delta = matter_delta;

            // Dark-matter dimple dilution: fossil dimples are geometric features of
            // space, so as the universe expands they stretch and shallow. Couple the
            // dilution to the scale-factor ratio this step, raised to a tunable
            // exponent (p=3 mimics matter-density dilution rho ~ a^-3). This is the
            // sink that bounds the otherwise-unconserved dimple field — without it
            // the GR-break deposit accumulates without limit and the gravity floor
            // rises unboundedly. Watch max_dimple/total_dimple below to confirm it
            // holds.
            if scale_factor > scale_factor_prev && scale_factor_prev > 0.0 {
                let dilution = (scale_factor_prev / scale_factor).powf(app_settings.dimple_dilution_exponent);
                grid.par_iter_mut().for_each(|col| {
                    col.iter_mut().for_each(|row| {
                        row.iter_mut().for_each(|cell| {
                            if cell.rip_dimple > 0.0 {
                                cell.rip_dimple *= dilution;
                            }
                        });
                    });
                });
            }

            // TEMP INSTRUMENT (darkmatter-phase1): watch the dimple field for runaway.
            // The dimple deposit is decoupled from mass (intentional GR break), so the
            // dilution above is the only thing bounding it. Print every 25 steps so a
            // 200-step smoke test gives ~8 readings of the trend. Remove once the
            // dilution is confirmed to hold the field bounded.
            if timestep % 25 == 0 {
                let mut max_dimple = 0.0_f64;
                let mut total_dimple = 0.0_f64;
                let mut dimpled_cells = 0usize;
                let mut lensing_candidates = 0usize;
                for col in grid.iter() {
                    for row in col.iter() {
                        for cell in row.iter() {
                            if cell.rip_dimple > 0.0 {
                                max_dimple = max_dimple.max(cell.rip_dimple);
                                total_dimple += cell.rip_dimple;
                                dimpled_cells += 1;
                            }
                            if cell.rip_dimple > app_settings.lensing_dimple_min && cell.matter_density < app_settings.lensing_matter_max && !cell.is_black_hole {
                                lensing_candidates += 1;
                            }
                        }
                    }
                }
                eprintln!(
                    "[t={}] dimple: max={:.4e} total={:.4e} cells={} lens={} | a={:.4}",
                    timestep, max_dimple, total_dimple, dimpled_cells, lensing_candidates, scale_factor
                );
            }

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
                                    set_as_black_hole(cell, &next_black_hole_id);
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

            // Tier 0 lensing diagnostic: flag cells holding gravitating dark
            // matter where baryonic matter is sparse — "mass where there is no
            // matter". Set on the final post-transport/dilution state so the
            // persisted flag matches what the plots read back.
            let lens_min = app_settings.lensing_dimple_min;
            let lens_max = app_settings.lensing_matter_max;
            grid.par_iter_mut().for_each(|col| {
                col.iter_mut().for_each(|row| {
                    row.iter_mut().for_each(|cell| {
                        cell.is_lensing_candidate = cell.rip_dimple > lens_min && cell.matter_density < lens_max && !cell.is_black_hole;
                    });
                });
            });

            db.save_all_cells(run.run_id, &mut grid).expect("Error saving cells");
            let active_galaxy_count = galaxies.iter().filter(|g| g.is_active).count() as i64;
            db.record_timestep_summary(timestep, 100.0, &grid, run.run_id, scale_factor, current_total_matter, active_galaxy_count)
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

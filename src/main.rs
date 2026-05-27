// use rand::{prelude::*, rngs::ThreadRng};
// use rayon::prelude::*;
// use std::fs::{File, create_dir_all};
// use std::io::Write;
// use std::path::Path;

use crate::database::app_settings::AppSettings;
use crate::database::database_setup::setup_database;

use crate::database::db_provider::DbProvider;
use crate::database::sqlite_provider::SqliteProvider;
use crate::enums::LogLevel;

mod create_data;
mod database;
mod enums;
/*
fn run_simulation(run_index: usize, app_settings: &AppSettings, db: &mut dyn DbProvider) {
    let start = std::time::Instant::now();
    let mut rng = thread_rng();
    let mut galaxies: Vec<Galaxy> = (0..app_settings.num_galaxies)
        .map(|_| Galaxy::new(app_settings))
        .collect();
    let mut global_rip_zone: f64 = 0.0;

    let dir = Path::new("data");
    if !dir.exists() {
        create_dir_all(dir).expect("Failed to create data directory");
    }

    let filename = format!("data/run_{}.csv", run_index);
    let mut output = File::create(&filename).expect("Failed to create run file");

    // Create the data file and run the simulation
    writeln!(output, "time_myr,rip_strength,scale_factor").unwrap();
    let mut buffer = String::new();

    let _ = db.log_message(
        "run_simulation",
        LogLevel::Info,
        format!(
            "Starting run {0} at {1}",
            run_index,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as f64
        )
        .as_str(),
    );

    for time_myr in (0..=app_settings.sim_duration).step_by(app_settings.time_step) {
        for galaxy in &mut galaxies {
            let lost_mass = galaxy.simulate_step(time_myr, app_settings, &mut rng);
            if lost_mass > 0.0 {
                global_rip_zone +=
                    lost_mass * app_settings.gravity / app_settings.light_speed.powi(2);
            }
        }

        let time_myr_f64 = time_myr as f64;

        let matter_density = if time_myr_f64 < app_settings.matter_fadeout_time_myr {
            1.0 / (1.0 + time_myr_f64).powf(1.5)
        } else {
            0.0 //  matter density: stop mattering after a lot of expansion
        };

        let scale_factor = (global_rip_zone + matter_density).powf(1.0 + app_settings.dark_energy);

        buffer.push_str(&format!(
            "{},{:.12e},{:.6}\n",
            time_myr, global_rip_zone, scale_factor
        ));
    }
    write!(output, "{}", buffer).unwrap();

    let duration = start.elapsed();
    let _ = db.log_message(
        "run_simulation",
        LogLevel::Info,
        format!(
            "Completed run {0} at {1} | Duration: {2:?}",
            run_index,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as f64,
            duration
        )
        .as_str(),
    );
}
*/

fn main() {
    let conn = setup_database(true).unwrap();
    let app_settings = AppSettings::get_settings(&conn);
    let mut db = SqliteProvider { conn };
    show_settings(&app_settings);
    let start = std::time::Instant::now();

    // If NUM_CORES is -1, use all available threads. Otherwise, set the limit.
    if app_settings.num_cores > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(app_settings.num_cores as usize)
            .build_global()
            .expect("Failed to build thread pool");
    }

    /*
    for run in 0..app_settings.num_runs {
        run_simulation(run, &app_settings, &mut db);
    }
    */
    let _ = create_data::run(&app_settings, &mut db);

    let duration = start.elapsed();
    println!("Simulated {} runs in {:?}", app_settings.num_runs, duration);
}

fn show_settings(settings: &AppSettings) {
    if !settings.quiet {
        println!("=== Simulation Configuration ===");
        println!("RIP_INITIAL:              {}", settings.rip_initial);
        println!("RIP_DECAY_RATE:           {}", settings.rip_decay_rate);
        println!(
            "RIP_MINIMUM_STRENGTH:     {}",
            settings.rip_minimum_strength
        );
        println!(
            "RIP_CURVATURE_WEIGHT:     {}",
            settings.rip_curvature_weight
        );
        println!("RIP_DENSITY_WEIGHT:       {}", settings.rip_density_weight);
        println!("DECAY_FACTOR:             {}", settings.decay_factor);
        println!("TIME_STEP_SIZE:           {}", settings.time_step_size);
        println!("MAX_SIMULATION_TIME:      {}", settings.max_simulation_time);
        println!("NUM_TIMESTEPS:            {}", settings.num_timesteps);
        println!("INF_GRID_WIDTH:           {}", settings.inf_grid_width);
        println!("INF_GRID_HEIGHT:          {}", settings.inf_grid_height);
        println!("INF_GRID_DEPTH:           {}", settings.inf_grid_depth);
        println!(
            "STRUCTURE_NUM_PARTICLES:  {}",
            settings.structure_num_particles
        );
        println!("CURVATURE_THRESHOLD:      {}", settings.curvature_threshold);
        println!(
            "COLLAPSE_DENSITY_THRESHOLD: {}",
            settings.collapse_density_threshold
        );
        println!("DARK_MATTER_RATIO:        {}", settings.dark_matter_ratio);
        println!("DARK_GRAVITY_BOOST:       {}", settings.dark_gravity_boost);
        println!("GRAVITY:                  {}", settings.gravity);
        println!("LIGHT_SPEED:              {}", settings.light_speed);
        println!("===============================");
    }
}

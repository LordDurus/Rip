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
mod initial_geometry;
mod populate_grid;
mod rip_helpers;

fn main() {
    let conn = setup_database(true).unwrap();
    let app_settings = AppSettings::get_settings(&conn);
    let mut db = SqliteProvider { conn };
    show_settings(&app_settings);
    let start = std::time::Instant::now();

    // If NUM_CORES is -1, use all available threads. Otherwise, set the limit.
    if app_settings.num_cores != 0 {
        rayon::ThreadPoolBuilder::new().num_threads(app_settings.num_cores as usize).build_global().expect("Failed to build thread pool");
    }

    let _ = create_data::run(&app_settings, &mut db);

    let duration = start.elapsed();
    println!("Simulated {} runs in {:?}", app_settings.num_runs, duration);
}

fn show_settings(settings: &AppSettings) {
    if !settings.quiet {
        println!("=== Simulation Configuration ===");
        println!("RIP_INITIAL:              {}", settings.rip_initial);
        println!("RIP_DECAY_RATE:           {}", settings.rip_decay_rate);
        println!("RIP_MINIMUM_STRENGTH:     {}", settings.rip_minimum_strength);
        println!("RIP_CURVATURE_WEIGHT:     {}", settings.rip_curvature_weight);
        println!("RIP_DENSITY_WEIGHT:       {}", settings.rip_density_weight);
        println!("DECAY_FACTOR:             {}", settings.decay_factor);
        println!("TIME_STEP_SIZE:           {}", settings.time_step_size);
        println!("MAX_SIMULATION_TIME:      {}", settings.max_simulation_time);
        println!("NUM_TIMESTEPS:            {}", settings.num_timesteps);
        println!("INF_GRID_WIDTH:           {}", settings.inf_grid_width);
        println!("INF_GRID_HEIGHT:          {}", settings.inf_grid_height);
        println!("INF_GRID_DEPTH:           {}", settings.inf_grid_depth);
        println!("STRUCTURE_NUM_PARTICLES:  {}", settings.structure_num_particles);
        println!("CURVATURE_THRESHOLD:      {}", settings.curvature_threshold);
        println!("COLLAPSE_DENSITY_THRESHOLD: {}", settings.collapse_density_threshold);
        println!("DARK_MATTER_RATIO:        {}", settings.dark_matter_ratio);
        println!("DARK_GRAVITY_BOOST:       {}", settings.dark_gravity_boost);
        println!("GRAVITY:                  {}", settings.gravity);
        println!("LIGHT_SPEED:              {}", settings.light_speed);
        println!("RIP_DECAY_MECHANISM:      {}", settings.rip_decay_mechanism);
        println!("===============================");
    }
}

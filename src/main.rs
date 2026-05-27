use dark_energy_config::{
    INITIAL_BH_MASS, MATTER_FADEOUT_TIME_MYR, NUM_CORES, NUM_GALAXIES, NUM_RUNS, SIM_DURATION,
    TIME_STEP, W_DARK_ENERGY,
};

use rand::{prelude::*, rngs::ThreadRng};
use rayon::prelude::*;
use std::fs::{File, create_dir_all};
use std::io::Write;
use std::path::Path;

use crate::database::app_settings::AppSettings;
use crate::database::database_setup::setup_database;

use crate::database::db_provider::DbProvider;
use crate::database::sqlite_provider::SqliteProvider;
use crate::enums::LogLevel;

mod dark_energy_config;
mod database;
mod enums;

#[derive(Debug)]
struct Galaxy {
    mass: f64,
    bh_mass: f64,
    rip_events: Vec<(usize, f64)>,
}

impl Galaxy {
    fn new(app_settings: &AppSettings) -> Self {
        Self {
            mass: app_settings.initial_mass,
            bh_mass: app_settings.initial_bh_mass,
            rip_events: Vec::new(),
        }
    }

    fn simulate_step(&mut self, time: usize, rng: &mut ThreadRng) -> f64 {
        let matter_inflow = self.random_inflow(rng);
        self.bh_mass += matter_inflow;
        self.mass -= matter_inflow;

        if self.rip_chance(time, rng) {
            let lost_mass = self.destroy_mass(matter_inflow);
            self.bh_mass -= lost_mass;
            self.rip_events.push((time, lost_mass));
            return lost_mass;
        }
        0.0
    }

    fn random_inflow(&self, rng: &mut ThreadRng) -> f64 {
        rng.gen_range(1e6..1e8)
    }

    fn rip_chance(&self, time: usize, rng: &mut ThreadRng) -> bool {
        let base_chance = 0.00009;
        let scale = (self.bh_mass / INITIAL_BH_MASS) * (time as f64 / SIM_DURATION as f64).ln_1p();
        rng.gen_bool((base_chance * scale).min(1.0))
    }

    fn destroy_mass(&self, mass: f64) -> f64 {
        let mut rng = rand::thread_rng();
        mass * rng.gen_range(0.1..=0.5)
    }
}

fn run_simulation(run_index: usize, app_settings: &AppSettings, db: &mut dyn DbProvider) {
    let start = std::time::Instant::now();
    let mut rng = thread_rng();
    let mut galaxies: Vec<Galaxy> = (0..NUM_GALAXIES)
        .map(|_| Galaxy::new(app_settings))
        .collect();
    let mut global_rip_field: f64 = 0.0;

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

    for time_myr in (0..=SIM_DURATION).step_by(TIME_STEP) {
        for galaxy in &mut galaxies {
            let lost_mass = galaxy.simulate_step(time_myr, &mut rng);
            if lost_mass > 0.0 {
                global_rip_field +=
                    lost_mass * app_settings.gravity / app_settings.light_speed.powi(2);
            }
        }

        let time_myr_f64 = time_myr as f64;

        let matter_density = if time_myr_f64 < MATTER_FADEOUT_TIME_MYR {
            1.0 / (1.0 + time_myr_f64).powf(1.5)
        } else {
            0.0 //  matter density: stop mattering after a lot of expansion
        };

        let scale_factor = (global_rip_field + matter_density).powf(1.0 + W_DARK_ENERGY);

        buffer.push_str(&format!(
            "{},{:.12e},{:.6}\n",
            time_myr, global_rip_field, scale_factor
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

fn main() {
    let conn = setup_database(true).unwrap();
    let settings = AppSettings::get_settings(&conn);
    let mut db = SqliteProvider { conn };
    show_settings(&settings);
    let start = std::time::Instant::now();

    // If NUM_CORES is -1, use all available threads. Otherwise, set the limit.
    if NUM_CORES > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(NUM_CORES as usize)
            .build_global()
            .expect("Failed to build thread pool");
    }

    for run in 0..NUM_RUNS {
        run_simulation(run, &settings, &mut db);
    }

    let duration = start.elapsed();
    println!("Simulated {} runs in {:?}", NUM_RUNS, duration);
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

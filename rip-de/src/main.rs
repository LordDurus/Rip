mod magic_numbers;
use chrono::offset::Local;
use magic_numbers::*;
use rand::{prelude::*, rngs::ThreadRng};
use rayon::prelude::*;
use std::fs::{File, create_dir_all};
use std::io::Write;
use std::path::Path;

#[derive(Debug)]
struct Galaxy {
    mass: f64,
    bh_mass: f64,
    rip_events: Vec<(usize, f64)>,
}

impl Galaxy {
    fn new() -> Self {
        Self {
            mass: INITIAL_MASS,
            bh_mass: INITIAL_BH_MASS,
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

fn update_rip_field(global_rip_field: f64, lost_mass: f64) -> f64 {
    let mut updated = global_rip_field + (lost_mass * G / LIGHT_SPEED.powi(2));
    updated *= DECAY_FACTOR;
    return updated;
}

fn run_simulation(run_index: usize) {
    let start = std::time::Instant::now();
    let mut rng = thread_rng();
    let mut galaxies: Vec<Galaxy> = (0..NUM_GALAXIES).map(|_| Galaxy::new()).collect();
    let mut global_rip_field: f64 = 0.0;

    let dir = Path::new("data");
    if !dir.exists() {
        create_dir_all(dir).expect("Failed to create data directory");
    }

    let filename = format!("data/run_{}.csv", run_index);
    let mut output = File::create(&filename).expect("Failed to create run file");

    // Create the data file and run the simulation
    writeln!(output, "time_myr,rip_field").unwrap();
    let mut buffer = String::new();
    for t in (0..=SIM_DURATION).step_by(TIME_STEP) {
        for galaxy in &mut galaxies {
            let lost_mass = galaxy.simulate_step(t, &mut rng);
            if lost_mass > 0.0 {
                global_rip_field = update_rip_field(global_rip_field, lost_mass);

                /*
                if !global_rip_field.is_finite() || global_rip_field > 1e100 {
                    println!(
                        "rip field overflow at time {} Myr in run {} — value: {:.2e}, lost_mass: {:.2e}, bh_mass: {:.2e}",
                        t, run_index, global_rip_field, lost_mass, galaxy.bh_mass
                    );
                    break;
                }
                */
            }
        }
        buffer.push_str(&format!("{},{:.12e}\n", t, global_rip_field));
    }
    write!(output, "{}", buffer).unwrap();

    let duration = start.elapsed();
    println!(
        "Completed run {} in {:?} | {}",
        run_index + 1,
        duration,
        filename
    );
}

fn main() {
    let start = std::time::Instant::now();
    println!("Simulation Started {}", Local::now());

    // If NUM_CORES is -1, use all available threads. Otherwise, set the limit.
    if NUM_CORES > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(NUM_CORES as usize)
            .build_global()
            .expect("Failed to build thread pool");
    }

    (0..NUM_RUNS).into_par_iter().for_each(|run| {
        run_simulation(run);
    });

    let duration = start.elapsed();
    println!("Simulated {} runs in {:?}", NUM_RUNS, duration);
}

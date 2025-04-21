use rand::{prelude::*, rngs::ThreadRng};
use std::fs::{File, create_dir_all};
use std::io::Write;
use std::path::Path;

// Gravitational constant in m^3 kg^-1 s^-2
const G: f64 = 6.67430e-11;

// Speed of light in meters per second
const LIGHT_SPEED: f64 = 3.0e8;

// Total initial mass of each galaxy in solar masses
const INITIAL_MASS: f64 = 1.0e12;

// Initial mass of the central black hole in each galaxy (solar masses)
const INITIAL_BH_MASS: f64 = 1.0e8;

// Number of galaxies simulated per run
const NUM_GALAXIES: usize = 1000;

// Duration of the simulation in million years
const SIM_DURATION: usize = 13_800;

// Time step of each simulation update (million years)
const TIME_STEP: usize = 100;

// Number of independent simulation runs
const NUM_RUNS: usize = 10;

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
    global_rip_field + (lost_mass * G / LIGHT_SPEED.powi(2))
}

fn run_simulation(run_index: usize) {
    let mut rng = thread_rng();
    let mut galaxies: Vec<Galaxy> = (0..NUM_GALAXIES).map(|_| Galaxy::new()).collect();
    let mut global_rip_field: f64 = 0.0;

    let dir = Path::new("data");
    if !dir.exists() {
        create_dir_all(dir).expect("Failed to create data directory");
    }

    let filename = format!("data/run_{}.csv", run_index);
    let mut output = File::create(&filename).expect("Failed to create run file");
    writeln!(output, "time_myr,rip_field").unwrap();

    for t in (0..=SIM_DURATION).step_by(TIME_STEP) {
        for galaxy in &mut galaxies {
            let lost_mass = galaxy.simulate_step(t, &mut rng);
            if lost_mass > 0.0 {
                global_rip_field = update_rip_field(global_rip_field, lost_mass);
            }
        }
        writeln!(output, "{},{:.12e}", t, global_rip_field).unwrap();
    }
    println!("Completed run {} | {}", run_index + 1, filename);
}

fn main() {
    for run in 0..NUM_RUNS {
        run_simulation(run);
    }
    println!("All {} simulations complete.", NUM_RUNS);
}

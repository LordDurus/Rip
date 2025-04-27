// Gravitational constant in m^3 kg^-1 s^-2
pub const G: f64 = 6.67430e-11;

// Speed of light in meters per second
pub const LIGHT_SPEED: f64 = 3.0e8;

// Total initial mass of each galaxy in solar masses
pub const INITIAL_MASS: f64 = 1.0e12;

// Initial mass of the central black hole in each galaxy (solar masses)
pub const INITIAL_BH_MASS: f64 = 1.0e8;

// Number of galaxies simulated per run
pub const NUM_GALAXIES: usize = 1000000;

// Duration of the simulation in million years
pub const SIM_DURATION: usize = 13_800;

// Time step of each simulation update (million years)
pub const TIME_STEP: usize = 100;

// Number of independent simulation runs
pub const NUM_RUNS: usize = 10;

// -1 for all available cores
pub const NUM_CORES: isize = -1;

// 0.01% decay per timestep
pub const DECAY_FACTOR: f64 = 0.9999;

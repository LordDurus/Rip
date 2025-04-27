/// Configuration constants specifically for dark energy simulations.

/// Total initial mass of each galaxy in solar masses.
pub const INITIAL_MASS: f64 = 1.0e12;

/// Initial mass of the central black hole in each galaxy (solar masses).
pub const INITIAL_BH_MASS: f64 = 1.0e8;

/// Number of galaxies simulated per run.
pub const NUM_GALAXIES: usize = 1_000_000;

/// Duration of the simulation in millions of years.
pub const SIM_DURATION: usize = 13_800;

/// Time step per simulation update (millions of years).
pub const TIME_STEP: usize = 100;

/// Number of independent simulation runs.
pub const NUM_RUNS: usize = 10;

/// Number of CPU cores to use (-1 = all available).
pub const NUM_CORES: isize = -1;

/// Fractional decay applied to rip field per time step (e.g., 0.9999 = 0.01% decay per step).
pub const DECAY_FACTOR: f64 = 0.9999;

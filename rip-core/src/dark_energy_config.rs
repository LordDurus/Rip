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

/// Equation of State parameter (w) describes the pressure-to-density ratio.
/// Different types of cosmic "stuff" have characteristic w values:
///
/// | Type of Stuff                 | Typical w Value | Behavior                                   |
/// |-------------------------------|-----------------|--------------------------------------------|
/// | Normal matter (dust)          | w = 0           | Slows expansion, gravity dominates         |
/// | Radiation (early universe)    | w = 1/3         | Expands faster (but still decelerates)     |
/// | Dark energy (cosmological constant) | w = -1    | Accelerated expansion                      |
/// | Phantom energy (hypothetical) | w < -1          | "Big Rip" universe destruction             |
///
/// Setting w = -1 models dark energy with constant density causing accelerated expansion.
pub const W_DARK_ENERGY: f64 = -1.0;

/// Time (in million years) after which matter density is negligible
pub const MATTER_FADEOUT_TIME_MYR: f64 = 5000.0;

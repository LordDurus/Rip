use rusqlite::{Connection, Result};
use std::collections::HashMap;

#[allow(dead_code)]
#[derive(Debug)]
pub enum AppValue {
    Float(f64),
    Int(i64),
    Bool(bool),
    Text(String),
    String(String),
}

#[derive(Debug)]
/// Holds configuration settings for the cosmological simulation.
pub struct AppSettings {
    /*
    /// Total initial mass of each galaxy in solar masses.
    pub initial_mass: f64,
    /// Initial mass of the central black hole in each galaxy (solar masses).
    pub initial_bh_mass: f64,
    /// Time (in million years) after which matter density is negligible
    pub matter_fadeout_time_myr: f64,
    /// Duration of the simulation in millions of years.
    pub sim_duration: usize,
    /// Number of galaxies simulated per run.
    pub num_galaxies: usize,
    */
    /// Gravitational constant used in force calculations.
    pub gravity: f64,
    /// Speed of light constant.    
    pub light_speed: f64,
    /// Legacy decay factor for initial experiments (may be deprecated).
    pub decay_factor: f64,
    /// Initial strength of the rip location before inflation effects.
    pub rip_initial: f64,
    /// Controls the exponential growth of the rip location during inflation.
    pub rip_decay_rate: f64,
    /// Minimum floor for rip location strength to prevent collapse to zero.
    pub rip_minimum_strength: f64,
    /// Duration of a single simulation step, in arbitrary time units.
    pub time_step_size: f64,
    /// Maximum simulation time before stopping, in the same units as time steps.
    pub max_simulation_time: f64,
    /// Proportion of dark matter relative to visible matter.
    pub dark_matter_ratio: f64,
    /// Amplification factor for gravity due to dark matter.
    pub dark_gravity_boost: f64,
    /// Width of the simulation grid (number of cells along x-axis).
    pub inf_grid_width: usize,
    /// Height of the simulation grid (number of cells along y-axis).
    pub inf_grid_height: usize,
    /// Depth of the simulation grid (number of cells along z-axis).
    pub inf_grid_depth: usize,
    /// Total number of simulation steps to run.
    pub num_timesteps: usize,
    /// Minimum curvature required to trigger collapse mechanisms.
    pub curvature_threshold: f64,
    /// Minimum density required to trigger collapse mechanisms.
    pub collapse_density_threshold: f64,
    /// Number of structure particles used in the simulation.
    pub structure_num_particles: usize,
    /// Suppress logging/output if true.
    pub quiet: bool,
    /// Weight of curvature's influence on local rip location amplification.
    pub rip_curvature_weight: f64,
    /// Weight of matter density's influence on local rip location amplification.
    pub rip_density_weight: f64,
    /// Controls the long-term exponential decay (self-healing) of the rip location.
    pub rip_evaporation_rate: f64,
    /// Number of independent simulation runs.
    pub num_runs: usize,

    /*
    /// Time step per simulation update (millions of years).///
    pub time_step: usize,
    */
    /// Number of CPU cores to use (-1 = all available).
    pub num_cores: isize,
    /*
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
    pub dark_energy: f64,
    */
}

impl AppSettings {
    pub fn load_dynamic(conn: &Connection) -> Result<HashMap<String, AppValue>> {
        let mut stmt =
            conn.prepare("select ltrim(rtrim(key)) as key, ltrim(trim(value)) as value, ltrim(rtrim(datatype)) as datatype from app_setting")?;

        let settings_iter = stmt.query_map([], |row| {
            let key: String = row.get(0)?;
            let val: String = row.get(1)?;
            let dtype: String = row.get(2)?;

            let parsed = match dtype.trim().to_lowercase().as_str() {
                "f64" => match val.parse::<f64>() {
                    Ok(v) => Ok(AppValue::Float(v)),
                    Err(e) => {
                        println!(
                            "Invalid float setting - key: {}, type: f64, value: {:?}",
                            key, val
                        );
                        return Err(rusqlite::Error::FromSqlConversionFailure(
                            0,
                            rusqlite::types::Type::Text,
                            Box::new(e),
                        ));
                    }
                },
                "int" => val.parse::<i64>().map(AppValue::Int).map_err(|e| {
                    rusqlite::Error::FromSqlConversionFailure(
                        0,
                        rusqlite::types::Type::Text,
                        Box::new(e),
                    )
                }),
                "bool" => match val.to_lowercase().as_str() {
                    "true" | "1" | "yes" | "y" => Ok(AppValue::Bool(true)),
                    "false" | "0" | "no" | "n" => Ok(AppValue::Bool(false)),
                    _ => Err(rusqlite::Error::InvalidQuery), // Or construct custom error
                },
                "string" => Ok(AppValue::Text(val)),
                _other => Err(rusqlite::Error::InvalidColumnType(
                    0,
                    dtype.clone(),
                    rusqlite::types::Type::Text,
                )),
            }?;

            return Ok((key, parsed));
        })?;

        let mut map = HashMap::new();
        for item in settings_iter {
            let (k, v) = item?;
            map.insert(k.to_uppercase(), v);
        }
        Ok(map)
    }

    pub fn from_map(map: &HashMap<String, AppValue>) -> Self {
        let get_f64 = |key: &str| -> f64 {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Float(v)) => *v,
                Some(AppValue::Int(v)) => *v as f64,
                Some(AppValue::Bool(v)) => {
                    if *v {
                        1.0
                    } else {
                        0.0
                    }
                }
                _ => panic!("Missing or invalid setting for key: {}", key),
            }
        };

        let get_usize = |key: &str| -> usize {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Int(v)) => *v as usize,
                Some(AppValue::Float(v)) => *v as usize,
                _ => panic!("Missing or invalid usize setting for key: {}", key),
            }
        };

        let get_bool = |key: &str| -> bool {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Bool(v)) => *v,
                Some(AppValue::String(v)) => match v.trim().to_lowercase().as_str() {
                    "true" | "1" | "y" => true,
                    "false" | "0" | "n" => false,
                    _ => panic!("Invalid string value for bool key: {}", key),
                },
                Some(AppValue::Int(v)) => *v != 0,
                Some(AppValue::Float(v)) => *v != 0.0,
                _ => panic!("Missing or invalid bool setting for key: {}", key),
            }
        };

        AppSettings {
            // initial_mass: get_f64("INITIAL_MASS"),
            // initial_bh_mass: get_f64("INITIAL_BH_MASS"),
            // matter_fadeout_time_myr: get_f64("MATTER_FADEOUT_TIME_MYR"),
            // sim_duration: get_usize("SIM_DURATION"),
            // NUM_GALAXIES: get_usize("NUM_GALAXIES"),
            // num_runs: get_usize("NUM_RUNS"),
            // time_step: get_usize("TIME_STEP"),
            // num_cores: get_isize("NUM_CORES"),
            // W_DARK_ENERGY: get_f64("W_DARK_ENERGY"),
            /*
            sim_duration: 13_800,
            initial_mass: 1.0e12,
            initial_bh_mass: 0.0,
            matter_fadeout_time_myr: 5000.0,
            num_galaxies: 1_000_000,
            */
            num_runs: 50,
            // time_step: 100,
            num_cores: -1,
            // dark_energy: -1.0,
            gravity: get_f64("GRAVITY"),
            light_speed: get_f64("LIGHT_SPEED"),
            decay_factor: get_f64("DECAY_FACTOR"),
            rip_initial: get_f64("RIP_INITIAL"),
            rip_decay_rate: get_f64("RIP_DECAY_RATE"),
            time_step_size: get_f64("TIME_STEP_SIZE"),
            max_simulation_time: get_f64("MAX_SIMULATION_TIME"),
            dark_matter_ratio: get_f64("DARK_MATTER_RATIO"),
            dark_gravity_boost: get_f64("DARK_GRAVITY_BOOST"),
            inf_grid_width: get_usize("INF_GRID_WIDTH"),
            inf_grid_height: get_usize("INF_GRID_HEIGHT"),
            inf_grid_depth: get_usize("INF_GRID_DEPTH"),
            num_timesteps: get_usize("NUM_TIMESTEPS"),
            curvature_threshold: get_f64("CURVATURE_THRESHOLD"),
            collapse_density_threshold: get_f64("COLLAPSE_DENSITY_THRESHOLD"),
            structure_num_particles: get_usize("STRUCTURE_NUM_PARTICLES"),
            rip_minimum_strength: get_f64("RIP_MINIMUM_STRENGTH"),
            quiet: get_bool("QUIET"),
            rip_curvature_weight: get_f64("RIP_CURVATURE_WEIGHT"),
            rip_density_weight: get_f64("RIP_DENSITY_WEIGHT"),
            rip_evaporation_rate: get_f64("RIP_EVAPORATION_RATE"),
        }
    }

    pub fn get_settings(conn: &Connection) -> Self {
        let map = AppSettings::load_dynamic(&conn).expect("Failed to load settings");
        AppSettings::from_map(&map)
    }
}

use rusqlite::{Connection, Result};
use std::collections::HashMap;

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
    /// Total initial mass of each galaxy in solar masses.
    pub initial_mass: f64,

    pub initial_bh_mass: f64,

    /// Gravitational constant used in force calculations.
    pub gravity: f64,
    /// Speed of light constant.    
    pub light_speed: f64,
    /// Legacy decay factor for initial experiments (may be deprecated).
    pub decay_factor: f64,
    /// Initial strength of the rip field before inflation effects.
    pub rip_initial: f64,
    /// Controls the exponential growth of the rip field during inflation.
    pub rip_decay_rate: f64,
    /// Minimum floor for rip field strength to prevent collapse to zero.
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
    /// Weight of curvature's influence on local rip field amplification.
    pub rip_curvature_weight: f64,
    /// Weight of matter density's influence on local rip field amplification.
    pub rip_density_weight: f64,
    /// Controls the long-term exponential decay (self-healing) of the rip field.
    pub rip_evaporation_rate: f64,
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
            initial_mass: 1.0e12,
            initial_bh_mass: 0.0,

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

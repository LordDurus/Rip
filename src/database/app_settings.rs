use rusqlite::{Connection, Result};
use serde::Serialize;
use std::collections::HashMap;

#[allow(dead_code)]
#[derive(Debug)]
pub enum AppValue {
    Float(f64),
    Int(i64),
    Bool(bool),
    Text(String),
}

#[allow(dead_code)]
#[derive(Debug, Serialize)]
/// Holds configuration settings for the cosmological simulation.
pub struct AppSettings {
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
    #[serde(skip)]
    pub quiet: bool,
    /// Weight of curvature's influence on local rip location amplification.
    pub rip_curvature_weight: f64,
    /// Weight of matter density's influence on local rip location amplification.
    pub rip_density_weight: f64,
    /// Controls the long-term exponential decay (self-healing) of the rip location.
    pub rip_evaporation_rate: f64,
    /// Number of independent simulation runs.
    pub num_runs: usize,
    pub initial_geometry: String,
    // Uniform params
    /// Constant matter density applied to every cell when geometry is "uniform".
    pub uniform_density: f64,
    // --- Gaussian blob params ---
    /// Number of gaussian density peaks scattered across the grid.
    pub blob_count: usize,
    /// Peak matter density at the center of each blob, before falloff.
    pub blob_peak_density: f64,
    /// Minimum standard deviation (spread) of a blob, in cell units.
    pub blob_sigma_min: f64,
    /// Maximum standard deviation (spread) of a blob, in cell units.
    pub blob_sigma_max: f64,
    // --- Perlin params ---
    /// Number of noise octaves summed; more octaves add finer detail at diminishing amplitude.
    pub perlin_octaves: u32,
    /// Base spatial frequency of the noise; higher values produce smaller, denser features.
    pub perlin_frequency: f64,
    /// Base amplitude of the first octave, scaling the overall density variation.
    pub perlin_amplitude: f64,
    /// Seed for the Perlin generator, making a given noise field reproducible.
    pub perlin_seed: u32,
    /// Number of CPU cores to use (-1 = all available).
    pub num_cores: u32,
    /// self_healing, matter_coupled, inverse_strength.
    pub rip_decay_mechanism: String,
    /// TimeOnly mechanism: fraction of rip strength lost per unit time.
    pub decay_time_rate: f64,
    /// SelfHealing mechanism: base healing rate when spacetime is undisturbed.
    pub decay_healing_base: f64,
    /// SelfHealing mechanism: how strongly local curvature and density slow healing.
    pub decay_healing_damping: f64,
    /// MatterCoupled mechanism: decay rate applied while matter density is below threshold.
    pub decay_matter_rate: f64,
    /// MatterCoupled mechanism: density above which the rip stops decaying (matter feeds it).
    pub decay_matter_threshold: f64,
    /// InverseStrength mechanism: scaling factor; stronger rips decay more slowly.
    pub decay_inverse_rate: f64,
    /// Rip strength above which a cell collapses into a rip-induced black hole.
    pub rip_induced_threshold: f64,
    /// Coefficient controlling how much curvature feeds into matter density growth per step.
    pub gravity_density_coupling: f64,
    /// Coefficient controlling how much matter density feeds into curvature growth per step.
    pub gravity_curvature_coupling: f64,
    /// Rate at which gravity pulls matter into denser regions each timestep.
    pub accretion_rate: f64,
    /// Rate at which the rip field drains matter out of normal spacetime each timestep.
    pub rip_drain_rate: f64,
    /// Scaling factor converting matter loss per timestep to expansion rate.
    pub matter_expansion_rate: f64,
    /// Rate at which black holes drain matter from the grid each timestep.
    pub bh_drain_rate: f64,
    /// Rate at which gravity-driven matter transport moves matter between cells each timestep
    pub transport_rate: f64,
    /// Minimum curvature required for supermassive black hole seeding (higher than curvature_threshold).
    pub smbh_curvature_threshold: f64,
    /// Base probability of SMBH formation at timestep 0, before time-decay is applied.
    pub smbh_formation_probability: f64,
    /// Decay timescale (in timesteps) for SMBH formation probability; smaller = more strongly early-biased.
    pub smbh_early_bias: f64,
    /// Initial matter density assigned to an SMBH on formation, representing rapid early feeding from the host. Should dominate local density to drive gravitational growth.
    pub smbh_initial_density: f64,
    /// Rate at which SMBHs accrete matter from their cell each timestep, added to the SMBH's density and subtracted from the cell's normal matter density.
    pub smbh_accretion_rate: f64,
    /// SMBH parent-connection mode: "tied_to_curvature" or "independent_draw".
    pub smbh_connection_mode: String,
    /// Feed-rate scale for the curvature-tied connection mode.
    pub smbh_connection_curvature_rate: f64,
    /// Feed-rate scale for the independent-draw connection mode.
    pub smbh_connection_independent_rate: f64,
    pub smbh_connection_alpha: f64,
}

impl AppSettings {
    pub fn load_dynamic(conn: &Connection) -> Result<HashMap<String, AppValue>> {
        let mut stmt = conn.prepare("select ltrim(rtrim(key)) as key, ltrim(trim(value)) as value, ltrim(rtrim(datatype)) as datatype from app_setting")?;

        let settings_iter = stmt.query_map([], |row| {
            let key: String = row.get(0)?;
            let val: String = row.get(1)?;
            let dtype: String = row.get(2)?;

            let parsed = match dtype.trim().to_lowercase().as_str() {
                "f64" => match val.parse::<f64>() {
                    Ok(v) => Ok(AppValue::Float(v)),
                    Err(e) => {
                        println!("Invalid float setting - key: {}, type: f64, value: {:?}", key, val);
                        return Err(rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(e)));
                    }
                },
                "int" | "i64" => val
                    .parse::<i64>()
                    .map(AppValue::Int)
                    .map_err(|e| rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(e))),
                "u32" => val.parse::<u32>().map(|v| AppValue::Int(v as i64)).map_err(|e| {
                    println!("Invalid u32 setting - key: {}, type: u32, value: {:?}", key, val);
                    rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(e))
                }),
                "bool" => match val.to_lowercase().as_str() {
                    "true" | "1" | "yes" | "y" => Ok(AppValue::Bool(true)),
                    "false" | "0" | "no" | "n" => Ok(AppValue::Bool(false)),
                    _ => Err(rusqlite::Error::InvalidQuery), // Or construct custom error
                },
                "text" => Ok(AppValue::Text(val)),
                _other => Err(rusqlite::Error::InvalidColumnType(0, dtype.clone(), rusqlite::types::Type::Text)),
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

        let get_u32 = |key: &str| -> u32 {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Int(v)) => *v as u32,
                Some(AppValue::Float(v)) => *v as u32,
                _ => panic!("Missing or invalid u32 setting for key: {}", key),
            }
        };

        let get_string = |key: &str| -> String {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Text(v)) => v.clone(),
                _ => panic!("Missing or invalid string setting for key: {}", key),
            }
        };

        let get_bool = |key: &str| -> bool {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Bool(v)) => *v,
                Some(AppValue::Int(v)) => *v != 0,
                Some(AppValue::Float(v)) => *v != 0.0,
                _ => panic!("Missing or invalid bool setting for key: {}", key),
            }
        };

        AppSettings {
            transport_rate: get_f64("TRANSPORT_RATE"),
            num_runs: get_usize("NUM_RUNS"),
            num_cores: get_u32("NUM_CORES"),
            matter_expansion_rate: get_f64("MATTER_EXPANSION_RATE"),
            rip_induced_threshold: get_f64("RIP_INDUCED_THRESHOLD"),
            accretion_rate: get_f64("ACCRETION_RATE"),
            rip_drain_rate: get_f64("RIP_DRAIN_RATE"),
            bh_drain_rate: get_f64("BH_DRAIN_RATE"),
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
            initial_geometry: get_string("INITIAL_GEOMETRY"),
            uniform_density: get_f64("UNIFORM_DENSITY"),
            blob_count: get_usize("BLOB_COUNT"),
            blob_peak_density: get_f64("BLOB_PEAK_DENSITY"),
            blob_sigma_min: get_f64("BLOB_SIGMA_MIN"),
            blob_sigma_max: get_f64("BLOB_SIGMA_MAX"),
            perlin_octaves: get_u32("PERLIN_OCTAVES"),
            perlin_frequency: get_f64("PERLIN_FREQUENCY"),
            perlin_amplitude: get_f64("PERLIN_AMPLITUDE"),
            perlin_seed: get_u32("PERLIN_SEED"),
            rip_decay_mechanism: get_string("RIP_DECAY_MECHANISM"),
            decay_time_rate: get_f64("DECAY_TIME_RATE"),
            decay_healing_base: get_f64("DECAY_HEALING_BASE"),
            decay_healing_damping: get_f64("DECAY_HEALING_DAMPING"),
            decay_matter_rate: get_f64("DECAY_MATTER_RATE"),
            decay_matter_threshold: get_f64("DECAY_MATTER_THRESHOLD"),
            decay_inverse_rate: get_f64("DECAY_INVERSE_RATE"),
            gravity_density_coupling: get_f64("GRAVITY_DENSITY_COUPLING"),
            gravity_curvature_coupling: get_f64("GRAVITY_CURVATURE_COUPLING"),
            smbh_curvature_threshold: get_f64("SMBH_CURVATURE_THRESHOLD"),
            smbh_formation_probability: get_f64("SMBH_FORMATION_PROBABILITY"),
            smbh_early_bias: get_f64("SMBH_EARLY_BIAS"),
            smbh_initial_density: get_f64("SMBH_INITIAL_DENSITY"),
            smbh_accretion_rate: get_f64("SMBH_ACCRETION_RATE"),
            smbh_connection_mode: get_string("SMBH_CONNECTION_MODE"),
            smbh_connection_curvature_rate: get_f64("SMBH_CONNECTION_CURVATURE_RATE"),
            smbh_connection_independent_rate: get_f64("SMBH_CONNECTION_INDEPENDENT_RATE"),
            smbh_connection_alpha: get_f64("SMBH_CONNECTION_ALPHA"),
        }
    }

    pub fn get_settings(conn: &Connection) -> Self {
        let map = AppSettings::load_dynamic(&conn).expect("Failed to load settings");
        AppSettings::from_map(&map)
    }
}

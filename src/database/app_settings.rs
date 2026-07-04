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
pub struct AppSetting {
    // Begin generated properties
    /// Rate at which gravity pulls matter into denser regions each timestep.
    pub accretion_rate: f64,
    /// Rate at which black holes drain matter from the grid each timestep.
    pub bh_drain_rate: f64,
    /// Peak matter density at the center of a bullet-cluster clump. Must exceed
    /// collapse_density_threshold or the clump never rips and grows no halo.
    pub bullet_clump_peak_density: f64,
    /// Gaussian spread (std dev, in cell units) of each bullet-cluster clump.
    pub bullet_clump_sigma: f64,
    /// Half-offset (cells) of each Bullet Cluster clump from box center along WIDTH. 0 = single
    /// clump at center (formation); >0 = a colliding pair at center +/- this.
    pub bullet_separation: usize,
    /// Minimum density required to trigger collapse mechanisms.
    pub collapse_density_threshold: f64,
    /// Minimum curvature required to trigger collapse mechanisms.
    pub curvature_threshold: f64,
    /// Amplification factor for gravity due to dark matter.
    pub dark_gravity_boost: f64,
    /// Proportion of dark matter relative to visible matter.
    pub dark_matter_ratio: f64,
    /// Diffusive mechanism: coefficient spreading rip strength into neighboring cells per step.
    /// Reserved -- RipDecayMechanism::Diffusive is not yet implemented and panics by design.
    pub decay_diffusion_coeff: f64,
    /// Legacy decay factor for initial experiments (may be deprecated).
    pub decay_factor: f64,
    /// SelfHealing mechanism: base healing rate when spacetime is undisturbed.
    pub decay_healing_base: f64,
    /// SelfHealing mechanism: how strongly local curvature and density slow healing.
    pub decay_healing_damping: f64,
    /// InverseStrength mechanism: scaling factor; stronger rips decay more slowly.
    pub decay_inverse_rate: f64,
    /// MatterCoupled mechanism: decay rate applied while matter density is below threshold.
    pub decay_matter_rate: f64,
    /// MatterCoupled mechanism: density above which the rip stops decaying (matter feeds it).
    pub decay_matter_threshold: f64,
    /// TimeOnly mechanism: fraction of rip strength lost per unit time.
    pub decay_time_rate: f64,
    /// Retained momentum fraction
    pub dimple_birth_velocity_scale: f64,
    /// Exponent p in the dimple dilution (a_prev/a_now)^p applied each step. p=3 mimics matter-
    /// density dilution rho ~ a^-3. This is the sink that bounds the (intentionally mass-
    /// decoupled) dimple field.
    pub dimple_dilution_exponent: f64,
    /// Fraction of ripped matter that persists as a fossil dark-matter dimple. The dimple
    /// gravitates but is not baryonic matter and does not enter the inflation calc. Start low
    /// (0.1) to minimally perturb validated physics.
    pub dimple_retention: f64,
    /// Rate at which the dark-matter dimple advects down the gravity gradient each step (Tier 1
    /// collisionless clustering). Mirrors transport_rate but acts on rip_dimple and ignores
    /// black-hole cells (the dimple passes through). 0.0 disables movement, recovering the pre-
    /// Tier-1 pure static fossil behavior.
    pub dimple_transport_rate: f64,
    /// Matter density threshold for a cell to be absorbed into an existing galaxy. Lower than
    /// galaxy_formation_density_threshold.
    pub galaxy_capture_density_threshold: f64,
    /// FoF linking density: a non-BH cell links into a galaxy when its matter_density >= this.
    /// Set above filament density so galaxies are the dense nodes, not the threads. The
    /// critical knob for galaxy_count.
    pub galaxy_fof_density_threshold: f64,
    /// Matter density a cell must reach for a new galaxy to form.
    pub galaxy_formation_density_threshold: f64,
    /// Fractional radius increase per unit of galaxy total_mass per timestep. new_radius =
    /// old_radius + total_mass * galaxy_mass_growth_rate
    pub galaxy_mass_growth_rate: f64,
    /// Minimum overlap fraction for a found component to inherit a prior galaxy's id.
    pub galaxy_match_min_overlap: f64,
    /// Fraction of (r_i + r_j) within which two galaxies trigger a merger.
    pub galaxy_merge_overlap_fraction: f64,
    /// Minimum linked-cell count for a component to count as a galaxy (noise filter).
    pub galaxy_min_cells: usize,
    /// Mass-based dominance criterion for intra-galaxy SMBH merging. A non-dominant SMBH is
    /// absorbed into the galaxy's most massive SMBH when its own mass is below this fraction of
    /// the dominant one's mass. e.g. 0.1 → any SMBH under 10% of the dominant SMBH's mass
    /// merges in. Drives emergent ~one-SMBH-per- galaxy: comparable-mass pairs (true post-
    /// merger duals) survive until one pulls ahead, so the steady state is ≈1 dominant with
    /// rare transient duals.
    pub galaxy_smbh_dominance_threshold: f64,
    /// Maximum fraction of galaxy total_mass a single SMBH can hold. e.g. 0.1 → SMBH capped at
    /// 10% of host galaxy mass.
    pub galaxy_smbh_mass_fraction_cap: f64,
    /// Competitive share below which an SMBH is considered stalled and merges into its galaxy's
    /// dominant SMBH. share = smbh_connection_strength / galaxy's total smbh connection
    /// strength
    pub galaxy_smbh_stall_share_threshold: f64,
    /// Ram-pressure drag strength. 0 = collisionless gas (passes through like dark matter -> no
    /// offset); >0 = gas shocks and lags at the collision interface.
    pub gas_drag_coefficient: f64,
    /// Master switch for the gas momentum channel. Off = validated over damped transport
    /// (apply_matter_transport); on = apply_gas_momentum (inertia + drag).
    pub gas_momentum_enabled: bool,
    /// Master switch for thermal gas pressure. Off = byte-identical to the validated rip-drain-
    /// bounded path (gravity + ram-pressure drag only); on = adds the isothermal pressure term
    /// above. The clean A/B: pressure off reproduces today's stability curve, pressure on adds
    /// Jeans support.
    pub gas_pressure_enabled: bool,
    /// Use velocity-signed one-sided (upwind) differences for the isothermal pressure gradient;
    /// false = original central differences (checkerboard-prone)
    pub gas_pressure_upwind: bool,
    /// Density threshold above which ram-pressure drag engages. Set above a single clump's peak
    /// so only the two-clump overlap pileup triggers the shock.
    pub gas_shock_density: f64,
    /// Isothermal sound speed for thermal gas pressure: P = c_s^2 * rho, giving an acceleration
    /// a = -c_s^2 * grad(rho) / rho that pushes gas down its own density gradient. This is the
    /// Jeans support the stability readout was always assuming. Units: cells per unit-time
    /// (same as the in-memory gas velocity field). Bounded by the sound Courant condition c_s *
    /// TIME_STEP_SIZE < CFL (0.25); past that the gas freezes rather than blowing up -- a
    /// visible signal to lower this or the timestep. Inert while gas_pressure_enabled is false.
    pub gas_sound_speed: f64,
    /// Number of gaussian density peaks scattered across the grid.
    pub gaussian_blob_count: usize,
    /// Peak matter density at the center of each blob, before falloff.
    pub gaussian_blob_peak_density: f64,
    /// Maximum standard deviation (spread) of a blob, in cell units.
    pub gaussian_blob_sigma_max: f64,
    /// Minimum standard deviation (spread) of a blob, in cell units.
    pub gaussian_blob_sigma_min: f64,
    /// Gravitational constant used in force calculations.
    pub gravity: f64,
    /// Coefficient controlling how much matter density feeds into curvature growth per step.
    pub gravity_curvature_coupling: f64,
    /// Coefficient controlling how much curvature feeds into matter density growth per step.
    pub gravity_density_coupling: f64,
    /// Depth of the simulation grid (number of cells along z-axis).
    pub inf_grid_depth: usize,
    /// Height of the simulation grid (number of cells along y-axis).
    pub inf_grid_height: usize,
    /// Width of the simulation grid (number of cells along x-axis).
    pub inf_grid_width: usize,
    /// Which initial matter geometry to seed: uniform, blobs/gaussian_blobs, perlin, custom, or
    /// bullet_cluster.
    pub initial_geometry: String,
    /// Lensing diagnostic: a cell is flagged is_lensing_candidate when its rip_dimple exceeds
    /// this AND matter_density is below lensing_matter_max — gravitating dark matter sitting
    /// where there is little baryonic matter ("lensing where there is no matter").
    pub lensing_dimple_min: f64,
    /// Lensing diagnostic: upper matter_density bound for a lensing candidate.
    pub lensing_matter_max: f64,
    /// Speed of light constant.
    pub light_speed: f64,
    /// Scaling factor converting matter loss per timestep to expansion rate.
    pub matter_expansion_rate: f64,
    /// Upper bound on the dark-matter dimple particle count (Tier 2). Once the cap is wired in,
    /// exceeding it triggers particle merging (conserving mass and momentum) to bound count and
    /// per-step cost; 0 = uncapped. Inert while use_dimple_particles is false.
    pub max_dimple_particles: u32,
    /// Maximum simulation time before stopping, in the same units as time steps.
    pub max_simulation_time: f64,
    /// Number of CPU cores to use (0 = all available).
    pub num_cores: u32,
    /// Total number of simulation steps to run.
    pub num_timesteps: usize,
    /// Base amplitude of the first octave, scaling the overall density variation.
    pub perlin_amplitude: f64,
    /// Base spatial frequency of the noise; higher values produce smaller, denser features.
    pub perlin_frequency: f64,
    /// Number of noise octaves summed; more octaves add finer detail at diminishing amplitude.
    pub perlin_octaves: u32,
    /// Seed for the Perlin generator, making a given noise field reproducible.
    pub perlin_seed: u32,
    /// Suppress logging/output if true.
    pub quiet: bool,
    /// Weight of curvature's influence on local rip location amplification.
    pub rip_curvature_weight: f64,
    /// self_healing, matter_coupled, inverse_strength.
    pub rip_decay_mechanism: String,
    /// Controls the exponential growth of the rip location during inflation.
    pub rip_decay_rate: f64,
    /// Weight of matter density's influence on local rip location amplification.
    pub rip_density_weight: f64,
    /// Rate at which the rip field drains matter out of normal spacetime each timestep.
    pub rip_drain_rate: f64,
    /// Controls the long-term exponential decay (self-healing) of the rip location.
    pub rip_evaporation_rate: f64,
    /// Rip strength above which a cell collapses into a rip-induced black hole.
    pub rip_induced_threshold: f64,
    /// Initial strength of the rip location before inflation effects.
    pub rip_initial: f64,
    /// Minimum floor for rip location strength to prevent collapse to zero.
    pub rip_minimum_strength: f64,
    /// Rnd seed value 0 for not assigned
    pub seed: u64,
    /// Rate at which SMBHs accrete matter from their cell each timestep, added to the SMBH's
    /// density and subtracted from the cell's normal matter density.
    pub smbh_accretion_rate: f64,
    /// Alpha parameter for the heavy-tailed distribution used in the independent-draw SMBH
    /// connection mode; smaller values produce a more extreme heavy tail, increasing the rarity
    /// of strong connections that lead to runaway SMBH growth.
    pub smbh_connection_alpha: f64,
    /// Feed-rate scale for the curvature-tied connection mode.
    pub smbh_connection_curvature_rate: f64,
    /// Feed-rate scale for the independent-draw connection mode.
    pub smbh_connection_independent_rate: f64,
    /// SMBH parent-connection mode: "tied_to_curvature" or "independent_draw".
    pub smbh_connection_mode: String,
    /// Minimum curvature required for supermassive black hole seeding (higher than
    /// curvature_threshold).
    pub smbh_curvature_threshold: f64,
    /// Decay timescale (in timesteps) for SMBH formation probability; smaller = more strongly
    /// early-biased.
    pub smbh_early_bias: f64,
    /// Base probability of SMBH formation at timestep 0, before time-decay is applied.
    pub smbh_formation_probability: f64,
    /// Initial matter density assigned to an SMBH on formation, representing rapid early
    /// feeding from the host. Should dominate local density to drive gravitational growth.
    pub smbh_initial_density: f64,
    /// Fractional matter loss per timestep due to stellar burning. Applied as: matter_density
    /// *= (1.0 - star_burn_rate) Burned matter stays in the cell as diffuse gas — does not
    /// leave the grid, so galaxy matter budget is unchanged.
    pub star_burn_rate: f64,
    /// Density below which a star ceases to be a star (drops back to diffuse gas). Should be
    /// less than star_formation_threshold to provide hysteresis and prevent rapid
    /// formation/extinction flickering.
    pub star_extinction_threshold: f64,
    /// Maximum |matter_delta| at which star formation is permitted. When matter loss rate
    /// exceeds this the universe is too hot/chaotic for gravitational collapse (analog of pre-
    /// recombination epoch). Extinction is always allowed regardless of this threshold.
    pub star_formation_max_matter_delta: f64,
    /// Minimum matter density for a cell to become a star. Must be below
    /// collapse_density_threshold (BH formation takes priority).
    pub star_formation_threshold: f64,
    /// Number of structure particles used in the simulation.
    pub structure_num_particles: usize,
    /// Duration of a single simulation step, in arbitrary time units.
    pub time_step_size: f64,
    /// Rate at which gravity-driven matter transport moves matter between cells each timestep
    pub transport_rate: f64,
    /// Constant matter density applied to every cell when geometry is "uniform".
    pub uniform_density: f64,
    /// Tier 2 dark-matter mode switch. When true, dark matter is carried by collisionless
    /// particles (particle-mesh) that scatter mass onto the grid to source gravity, and
    /// rip_dimple becomes their projection. When false, the validated Tier 1 grid path runs
    /// unchanged (set DIMPLE_TRANSPORT_RATE to 0 in particle mode; non-zero for the Tier 1
    /// advection fallback).
    pub use_dimple_particles: bool,
    // End generated properties
}

impl AppSetting {
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
                "int" | "i64" | "usize" | "u64" => val
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
                    _ => {
                        println!("Invalid bool setting - key: {}, type: bool, value: {:?}", key, val);
                        Err(rusqlite::Error::InvalidQuery)
                    }
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
        let get_u64 = |key: &str| -> u64 {
            match map.get(&key.to_uppercase()) {
                Some(AppValue::Int(v)) => *v as u64,
                Some(AppValue::Float(v)) => *v as u64,
                _ => panic!("Missing or invalid u64 setting for key: {}", key),
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

        AppSetting {
            // Begin setting generated properties
            accretion_rate: get_f64("ACCRETION_RATE"),
            bh_drain_rate: get_f64("BH_DRAIN_RATE"),
            bullet_clump_peak_density: get_f64("BULLET_CLUMP_PEAK_DENSITY"),
            bullet_clump_sigma: get_f64("BULLET_CLUMP_SIGMA"),
            bullet_separation: get_usize("BULLET_SEPARATION"),
            collapse_density_threshold: get_f64("COLLAPSE_DENSITY_THRESHOLD"),
            curvature_threshold: get_f64("CURVATURE_THRESHOLD"),
            dark_gravity_boost: get_f64("DARK_GRAVITY_BOOST"),
            dark_matter_ratio: get_f64("DARK_MATTER_RATIO"),
            decay_diffusion_coeff: get_f64("DECAY_DIFFUSION_COEFF"),
            decay_factor: get_f64("DECAY_FACTOR"),
            decay_healing_base: get_f64("DECAY_HEALING_BASE"),
            decay_healing_damping: get_f64("DECAY_HEALING_DAMPING"),
            decay_inverse_rate: get_f64("DECAY_INVERSE_RATE"),
            decay_matter_rate: get_f64("DECAY_MATTER_RATE"),
            decay_matter_threshold: get_f64("DECAY_MATTER_THRESHOLD"),
            decay_time_rate: get_f64("DECAY_TIME_RATE"),
            dimple_birth_velocity_scale: get_f64("DIMPLE_BIRTH_VELOCITY_SCALE"),
            dimple_dilution_exponent: get_f64("DIMPLE_DILUTION_EXPONENT"),
            dimple_retention: get_f64("DIMPLE_RETENTION"),
            dimple_transport_rate: get_f64("DIMPLE_TRANSPORT_RATE"),
            galaxy_capture_density_threshold: get_f64("GALAXY_CAPTURE_DENSITY_THRESHOLD"),
            galaxy_fof_density_threshold: get_f64("GALAXY_FOF_DENSITY_THRESHOLD"),
            galaxy_formation_density_threshold: get_f64("GALAXY_FORMATION_DENSITY_THRESHOLD"),
            galaxy_mass_growth_rate: get_f64("GALAXY_MASS_GROWTH_RATE"),
            galaxy_match_min_overlap: get_f64("GALAXY_MATCH_MIN_OVERLAP"),
            galaxy_merge_overlap_fraction: get_f64("GALAXY_MERGE_OVERLAP_FRACTION"),
            galaxy_min_cells: get_usize("GALAXY_MIN_CELLS"),
            galaxy_smbh_dominance_threshold: get_f64("GALAXY_SMBH_DOMINANCE_THRESHOLD"),
            galaxy_smbh_mass_fraction_cap: get_f64("GALAXY_SMBH_MASS_FRACTION_CAP"),
            galaxy_smbh_stall_share_threshold: get_f64("GALAXY_SMBH_STALL_SHARE_THRESHOLD"),
            gas_drag_coefficient: get_f64("GAS_DRAG_COEFFICIENT"),
            gas_momentum_enabled: get_bool("GAS_MOMENTUM_ENABLED"),
            gas_pressure_enabled: get_bool("GAS_PRESSURE_ENABLED"),
            gas_pressure_upwind: get_bool("GAS_PRESSURE_UPWIND"),
            gas_shock_density: get_f64("GAS_SHOCK_DENSITY"),
            gas_sound_speed: get_f64("GAS_SOUND_SPEED"),
            gaussian_blob_count: get_usize("GAUSSIAN_BLOB_COUNT"),
            gaussian_blob_peak_density: get_f64("GAUSSIAN_BLOB_PEAK_DENSITY"),
            gaussian_blob_sigma_max: get_f64("GAUSSIAN_BLOB_SIGMA_MAX"),
            gaussian_blob_sigma_min: get_f64("GAUSSIAN_BLOB_SIGMA_MIN"),
            gravity: get_f64("GRAVITY"),
            gravity_curvature_coupling: get_f64("GRAVITY_CURVATURE_COUPLING"),
            gravity_density_coupling: get_f64("GRAVITY_DENSITY_COUPLING"),
            inf_grid_depth: get_usize("INF_GRID_DEPTH"),
            inf_grid_height: get_usize("INF_GRID_HEIGHT"),
            inf_grid_width: get_usize("INF_GRID_WIDTH"),
            initial_geometry: get_string("INITIAL_GEOMETRY"),
            lensing_dimple_min: get_f64("LENSING_DIMPLE_MIN"),
            lensing_matter_max: get_f64("LENSING_MATTER_MAX"),
            light_speed: get_f64("LIGHT_SPEED"),
            matter_expansion_rate: get_f64("MATTER_EXPANSION_RATE"),
            max_dimple_particles: get_u32("MAX_DIMPLE_PARTICLES"),
            max_simulation_time: get_f64("MAX_SIMULATION_TIME"),
            num_cores: get_u32("NUM_CORES"),
            num_timesteps: get_usize("NUM_TIMESTEPS"),
            perlin_amplitude: get_f64("PERLIN_AMPLITUDE"),
            perlin_frequency: get_f64("PERLIN_FREQUENCY"),
            perlin_octaves: get_u32("PERLIN_OCTAVES"),
            perlin_seed: get_u32("PERLIN_SEED"),
            quiet: get_bool("QUIET"),
            rip_curvature_weight: get_f64("RIP_CURVATURE_WEIGHT"),
            rip_decay_mechanism: get_string("RIP_DECAY_MECHANISM"),
            rip_decay_rate: get_f64("RIP_DECAY_RATE"),
            rip_density_weight: get_f64("RIP_DENSITY_WEIGHT"),
            rip_drain_rate: get_f64("RIP_DRAIN_RATE"),
            rip_evaporation_rate: get_f64("RIP_EVAPORATION_RATE"),
            rip_induced_threshold: get_f64("RIP_INDUCED_THRESHOLD"),
            rip_initial: get_f64("RIP_INITIAL"),
            rip_minimum_strength: get_f64("RIP_MINIMUM_STRENGTH"),
            seed: get_u64("SEED"),
            smbh_accretion_rate: get_f64("SMBH_ACCRETION_RATE"),
            smbh_connection_alpha: get_f64("SMBH_CONNECTION_ALPHA"),
            smbh_connection_curvature_rate: get_f64("SMBH_CONNECTION_CURVATURE_RATE"),
            smbh_connection_independent_rate: get_f64("SMBH_CONNECTION_INDEPENDENT_RATE"),
            smbh_connection_mode: get_string("SMBH_CONNECTION_MODE"),
            smbh_curvature_threshold: get_f64("SMBH_CURVATURE_THRESHOLD"),
            smbh_early_bias: get_f64("SMBH_EARLY_BIAS"),
            smbh_formation_probability: get_f64("SMBH_FORMATION_PROBABILITY"),
            smbh_initial_density: get_f64("SMBH_INITIAL_DENSITY"),
            star_burn_rate: get_f64("STAR_BURN_RATE"),
            star_extinction_threshold: get_f64("STAR_EXTINCTION_THRESHOLD"),
            star_formation_max_matter_delta: get_f64("STAR_FORMATION_MAX_MATTER_DELTA"),
            star_formation_threshold: get_f64("STAR_FORMATION_THRESHOLD"),
            structure_num_particles: get_usize("STRUCTURE_NUM_PARTICLES"),
            time_step_size: get_f64("TIME_STEP_SIZE"),
            transport_rate: get_f64("TRANSPORT_RATE"),
            uniform_density: get_f64("UNIFORM_DENSITY"),
            use_dimple_particles: get_bool("USE_DIMPLE_PARTICLES"),
            // End setting generated properties
        }
    }

    pub fn get_settings(conn: &Connection) -> Self {
        let map = AppSetting::load_dynamic(&conn).expect("Failed to load settings");
        AppSetting::from_map(&map)
    }
}

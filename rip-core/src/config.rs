/// Shared simulation configuration for rip field-based models.
#[derive(Debug, Clone, Copy)]
pub struct SimulationConfig {
    /// Initial rip field strength (arbitrary units).
    pub rip_initial: f64,
    /// Decay rate of the rip field per unit time (dimensionless).
    pub rip_decay_rate: f64,
    /// Time step size per simulation iteration (no units).
    pub time_step_size: f64,
    /// Maximum simulation time (no units).
    pub max_simulation_time: f64,
}

impl SimulationConfig {
    /// Default rip inflation configuration.
    pub fn default() -> Self {
        Self {
            rip_initial: 1e4,
            rip_decay_rate: 5.0,
            time_step_size: 0.01,
            max_simulation_time: 10.0,
        }
    }

    /// Faster rip decay for short inflation.
    pub fn fast_inflation() -> Self {
        Self {
            rip_initial: 1e4,
            rip_decay_rate: 7.0,
            time_step_size: 0.01,
            max_simulation_time: 5.0,
        }
    }

    /// Slower rip decay for long inflation.
    pub fn slow_inflation() -> Self {
        Self {
            rip_initial: 1e4,
            rip_decay_rate: 2.0,
            time_step_size: 0.01,
            max_simulation_time: 20.0,
        }
    }

    /// Build a custom configuration.
    pub fn from_parameters(
        rip_initial: f64,
        rip_decay_rate: f64,
        time_step_size: f64,
        max_simulation_time: f64,
    ) -> Self {
        Self {
            rip_initial,
            rip_decay_rate,
            time_step_size,
            max_simulation_time,
        }
    }
}

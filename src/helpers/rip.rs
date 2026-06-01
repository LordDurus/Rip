use crate::database::app_settings::AppSettings;
use crate::database::entities::cell::Cell;

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub enum RipDecayMechanism {
    /// Rip strength decays purely as a function of time. The original formula.
    /// Models: "rips dissipate because that's how spacetime works."
    TimeOnly { rate: f64 },

    /// Self-healing — spacetime actively repairs itself, faster when undisturbed.
    /// Models: "spacetime has a stiffness; tears mend when nothing's pulling on them."
    SelfHealing { base_rate: f64, density_damping: f64 },

    /// Matter-coupled — decay depends on matter lost into/through the rip.
    /// Models: "rips persist as long as they're being fed; starve them and they close."
    MatterCoupled { rate: f64, matter_threshold: f64 },

    /// Hawking-style — strong rips persist much longer than weak ones.
    /// Models: "rips are like black holes — bigger ones radiate more slowly."
    InverseStrength { rate: f64 },

    /// Diffusive — rip strength spreads to neighbors rather than disappearing.
    /// Models: "rips don't decay so much as smear out; total rippiness conserved."
    Diffusive { diffusion_coefficient: f64 },

    /// No decay at all — rips persist forever.
    /// Models: "once torn, always torn. Useful baseline."
    None,
}

impl RipDecayMechanism {
    /// Build from settings. Panics if the chosen mechanism's required params are missing
    /// — this is a startup-time configuration error.
    pub fn from_settings(settings: &AppSettings) -> Self {
        match settings.rip_decay_mechanism.to_lowercase().as_str() {
            "none" => Self::None,

            "time_only" | "time" => Self::TimeOnly { rate: settings.decay_time_rate },

            "self_healing" | "healing" => Self::SelfHealing {
                base_rate: settings.decay_healing_base,
                density_damping: settings.decay_healing_damping,
            },

            "matter_coupled" | "matter" => Self::MatterCoupled {
                rate: settings.decay_matter_rate,
                matter_threshold: settings.decay_matter_threshold,
            },

            "inverse_strength" | "inverse" => Self::InverseStrength { rate: settings.decay_inverse_rate },

            "diffusive" | "diffuse" => panic!("RIP_DECAY_MECHANISM 'diffusive' is not yet implemented. | Please choose: none, time_only, self_healing, matter_coupled, inverse_strength"),

            other => panic!("Unknown RIP_DECAY_MECHANISM: '{}'. Expected: none, time_only, self_healing, matter_coupled, inverse_strength", other),
        }
    }
}

pub fn compute_rip_decay(mechanism: &RipDecayMechanism, cell: &Cell, current_rip: f64, _timestep: usize, step_duration: f64) -> f64 {
    match mechanism {
        RipDecayMechanism::None => 0.0,

        RipDecayMechanism::TimeOnly { rate } => current_rip * rate * step_duration,

        RipDecayMechanism::SelfHealing { base_rate, density_damping } => {
            let local_resistance = 1.0 + density_damping * (cell.curvature + cell.matter_density);
            current_rip * base_rate * local_resistance * step_duration
        }

        RipDecayMechanism::MatterCoupled { rate, matter_threshold } => {
            if cell.matter_density < *matter_threshold {
                current_rip * rate * step_duration
            } else {
                0.0
            }
        }

        RipDecayMechanism::InverseStrength { rate } => {
            let safe = current_rip.max(1e-6);
            (rate / safe) * step_duration
        }

        RipDecayMechanism::Diffusive { .. } => 0.0, // handled in a separate pass
    }
}

#[inline(always)]
pub fn compute_cell_rip_strength(timestep: usize, cell: &Cell, settings: &AppSettings, decay_mechanism: &RipDecayMechanism, step_duration: f64) -> f64 {
    if cell.is_black_hole {
        return 0.0; // or some sentinel; black holes don't follow this formula
    }

    let ramp = 1.0 - f64::exp(-settings.rip_decay_rate * timestep as f64);
    let healing = 1.0 / (1.0 + cell.curvature + cell.matter_density);
    let rip_strength = settings.rip_initial * ramp * healing;
    let modifier = 1.0 + settings.rip_curvature_weight * cell.curvature + settings.rip_density_weight * cell.matter_density;

    let natural_strength = rip_strength * modifier;

    // Apply mechanism-based decay
    let decay = compute_rip_decay(decay_mechanism, cell, natural_strength, timestep, step_duration);

    (natural_strength - decay).clamp(settings.rip_minimum_strength, 1.0e6)
}

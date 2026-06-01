use crate::AppSettings;

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

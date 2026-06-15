use crate::AppSetting;
#[derive(Debug, Clone)]
pub enum SmbhConnectionMode {
    /// connection_strength = (curvature - smbh_curvature_threshold) × heavy_tailed_sampl
    TiedToCurvature { rate: f64 },
    /// connection_strength = heavy_tailed_sample
    IndependentDraw { rate: f64 },
}

impl SmbhConnectionMode {
    /// Build from settings. Panics if the chosen mechanism's required params are missing
    /// — this is a startup-time configuration error.
    pub fn from_settings(settings: &AppSetting) -> Self {
        match settings.smbh_connection_mode.to_lowercase().as_str() {
            "tied_to_curvature" | "curvature" => Self::TiedToCurvature {
                rate: settings.smbh_connection_curvature_rate,
            },
            "independent_draw" | "independent" => Self::IndependentDraw {
                rate: settings.smbh_connection_independent_rate,
            },

            other => panic!("Unknown SMBH_CONNECTION_MODE: '{}'. Expected: tied_to_curvature, independent_draw", other),
        }
    }
}

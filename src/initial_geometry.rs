use crate::database::app_settings::AppSetting;

#[derive(Debug, Clone)]
pub enum InitialGeometry {
    Uniform { density: f64 },
    GaussianBlobs { count: usize, peak_density: f64, sigma_min: f64, sigma_max: f64 },
    Perlin { octaves: u32, frequency: f64, amplitude: f64, seed: u32 },
    Custom, // Reads from custom_density table
}

impl InitialGeometry {
    /// Build from settings. Panics if the chosen geometry's required params are missing
    /// — which is what you want, since this is a startup-time configuration error.
    pub fn from_settings(settings: &AppSetting) -> Self {
        match settings.initial_geometry.to_lowercase().as_str() {
            "uniform" => Self::Uniform { density: settings.uniform_density },
            "blobs" | "gaussian_blobs" => Self::GaussianBlobs {
                count: settings.blob_count,
                peak_density: settings.blob_peak_density,
                sigma_min: settings.blob_sigma_min,
                sigma_max: settings.blob_sigma_max,
            },
            "perlin" => Self::Perlin {
                octaves: settings.perlin_octaves,
                frequency: settings.perlin_frequency,
                amplitude: settings.perlin_amplitude,
                seed: settings.perlin_seed,
            },
            "custom" => Self::Custom,
            other => panic!("Unknown INITIAL_GEOMETRY: '{}'. Expected: uniform, blobs, perlin, custom", other),
        }
    }
}

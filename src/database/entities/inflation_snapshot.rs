#[derive(Debug, Clone)]
pub struct InflationSnapshot {
    pub timestep: usize,
    pub scale_factor: f64,
    pub rip_strength: f64,
    pub average_density: f64,
    pub average_curvature: f64,
    pub black_hole_count: usize,
    pub gravity_well_sum: f64,
}

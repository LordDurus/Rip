use crate::database::entities::cell_position::CellPosition;

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct Cell {
    /// Unique identifier for this cell in the database
    pub cell_id: i64,
    /// 3D grid coordinates of this cell
    pub position: CellPosition,
    /// Simulation timestep at which this cell state was recorded
    pub timestep: usize,
    /// Strength of the rip field in this cell
    pub rip_strength: f64,
    /// Local curvature of spacetime at this cell
    pub curvature: f64,
    /// Mass density of matter within the cell
    pub matter_density: f64,
    /// True if this cell has collapsed into a black hole
    pub is_black_hole: bool,
    // Optional ID if the cell is part of a black hole
    pub black_hole_id: Option<u64>,
    /// Z-layer index within the 3D grid
    pub layer: usize,
    /// Cosmological scale factor at this timestep
    pub scale_factor: f64,
    /// X-component of the gravitational vector at this cell
    pub gravity_x: f64,
    /// Y-component of the gravitational vector at this cell
    pub gravity_y: f64,
    /// Z-component of the gravitational vector at this cell
    pub gravity_z: f64,
    /// Calculated per cell after inflation (can be negative)
    pub dimple_strength: f64,
    ///	Ff strong dimple + low matter density
    pub is_lensing_candidate: bool,
    /// Is this cell is an SMBH (mass exceeds threshold)
    pub is_supermassive: bool,
    /// Total mass in the cell
    pub mass: f64,
    /// The amount this cell contributes to the dark energy rip field
    pub smbh_rip_contribution: bool,
    /// True if this black hole was created due to rip-induced collapse (not from natural matter collapse)
    pub is_rip_induced: bool,
    /// Physical volume of the cell in simulated space
    pub volume: f64,
}

impl Cell {
    pub fn new() -> Self {
        Self {
            cell_id: 0,
            position: CellPosition { col: 0, row: 0, cell_position_id: 0 },
            layer: 0,
            timestep: 0,
            rip_strength: 0.0,
            curvature: 0.0,
            matter_density: 0.0,
            is_black_hole: false,
            black_hole_id: None,
            scale_factor: 0.0,
            gravity_x: 0.0,
            gravity_y: 0.0,
            gravity_z: 0.0,
            dimple_strength: 0.0,
            is_lensing_candidate: false,
            is_supermassive: false,
            mass: 0.0,
            smbh_rip_contribution: false,
            volume: 1.0,
            is_rip_induced: false,
        }
    }

    #[inline(always)]
    pub fn apply_gravity_interaction(&mut self) {
        self.matter_density += 0.05 * self.curvature;
        self.curvature += 0.005 * self.matter_density;
    }

    #[inline(always)]
    pub fn compute_gravity_from_density(&mut self, height: usize, width: usize, depth: usize, raw_density: &Vec<Vec<Vec<f64>>>, grid_width: usize, grid_height: usize, grid_depth: usize) {
        let dx = if width > 0 && width + 1 < grid_width {
            (raw_density[height][width + 1][depth] - raw_density[height][width - 1][depth]) / 2.0
        } else {
            0.0
        };

        let dy = if height > 0 && height + 1 < grid_height {
            (raw_density[height + 1][width][depth] - raw_density[height - 1][width][depth]) / 2.0
        } else {
            0.0
        };

        let dz = if depth > 0 && depth + 1 < grid_depth {
            (raw_density[height][width][depth + 1] - raw_density[height][width][depth - 1]) / 2.0
        } else {
            0.0
        };

        // negative gradient = pull toward higher density
        self.gravity_x = -dx;
        self.gravity_y = -dy;
        self.gravity_z = -dz;
    }
}

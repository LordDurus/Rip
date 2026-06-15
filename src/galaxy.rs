use crate::database::app_settings::AppSetting;
use crate::database::entities::cell::Cell;
use rand::Rng;

/// A persistent galaxy region. Created when a cell cluster exceeds the
/// formation density threshold. Updated every timestep — radius grows
/// based on total mass, cells within capture radius are absorbed, and
/// galaxies that overlap merge (smaller is marked inactive).
#[derive(Debug, Clone)]
pub struct Galaxy {
    pub galaxy_id: i64,
    pub run_id: i64,
    pub formed_timestep: usize,

    /// Centroid in grid coordinates (real-valued, updated each timestep).
    pub centroid_col: f64,
    pub centroid_row: f64,
    pub centroid_layer: f64,

    /// Current capture radius in cells.
    pub radius: f64,
    pub total_mass: f64,
    pub stellar_mass: f64,
    pub smbh_mass: f64,
    pub cell_count: usize,

    /// Multiplicative matter-density boost applied at initialisation.
    /// Set from app_settings.galaxy_overdensity at seed time; not updated thereafter.
    pub overdensity_boost: f64,

    /// False once this galaxy has been absorbed by a merger.
    pub is_active: bool,
}

/// Place `count` galaxy seeds at random positions in the grid.
/// Called once from `seed_initial_curvature` before the timestep loop.
/// Returns Vec<Galaxy> with negative galaxy_ids (not yet persisted to DB).
pub fn place_galaxies(grid_height: usize, grid_width: usize, grid_depth: usize, count: usize, radius: f64, overdensity_boost: f64, rng: &mut impl Rng) -> Vec<Galaxy> {
    (0..count)
        .map(|i| {
            let col = rng.gen_range(0..grid_height) as f64;
            let row = rng.gen_range(0..grid_width) as f64;
            let layer = rng.gen_range(0..grid_depth) as f64;
            Galaxy {
                galaxy_id: -(i as i64 + 1),
                run_id: 0, // filled in after run is started
                formed_timestep: 0,
                centroid_col: col,
                centroid_row: row,
                centroid_layer: layer,
                radius,
                total_mass: 0.0,
                stellar_mass: 0.0,
                smbh_mass: 0.0,
                cell_count: 0,
                overdensity_boost,
                is_active: true,
            }
        })
        .collect()
}

impl Galaxy {
    /// Stamp run_id onto galaxies placed before the run was started.
    /// Called immediately after `db.start_run()` so all galaxies carry the correct run_id.
    pub fn assign_run_id(galaxies: &mut Vec<Galaxy>, run_id: i64) {
        for g in galaxies.iter_mut() {
            g.run_id = run_id;
        }
    }

    /// Scan the grid for new overdensity seeds not yet claimed by any
    /// active galaxy. Called each timestep to allow late-forming galaxies.
    pub fn discover_new(grid: &[Vec<Vec<Cell>>], existing: &[Galaxy], app_settings: &AppSetting, timestep: usize, run_id: i64, next_id: &mut i64) -> Vec<Galaxy> {
        let mut new_galaxies: Vec<Galaxy> = Vec::new();

        for (col, col_cells) in grid.iter().enumerate() {
            for (row, row_cells) in col_cells.iter().enumerate() {
                for (layer, cell) in row_cells.iter().enumerate() {
                    if cell.is_black_hole {
                        continue;
                    }
                    if cell.matter_density < app_settings.galaxy_formation_density_threshold {
                        continue;
                    }
                    // Already inside an active galaxy?
                    let claimed = existing.iter().chain(new_galaxies.iter()).any(|g| g.is_active && g.contains(col, row, layer));
                    if claimed {
                        continue;
                    }

                    *next_id -= 1; // still negative until persisted
                    new_galaxies.push(Galaxy {
                        galaxy_id: *next_id,
                        run_id,
                        formed_timestep: timestep,
                        centroid_col: col as f64,
                        centroid_row: row as f64,
                        centroid_layer: layer as f64,
                        radius: app_settings.galaxy_radius,
                        total_mass: cell.matter_density,
                        stellar_mass: if cell.is_star { cell.matter_density } else { 0.0 },
                        smbh_mass: 0.0,
                        cell_count: 1,
                        overdensity_boost: 1.0, // late-forming galaxies don't get init boost
                        is_active: true,
                    });
                }
            }
        }

        new_galaxies
    }

    /// Update this galaxy's mass, centroid, and radius from the current grid.
    /// Returns the new total_mass so the caller can use it for the SMBH cap.
    pub fn update(&mut self, grid: &[Vec<Vec<Cell>>], app_settings: &AppSetting) {
        let mut total_mass = 0.0_f64;
        let mut stellar_mass = 0.0_f64;
        let mut smbh_mass = 0.0_f64;
        let mut cell_count = 0_usize;
        let mut cx = 0.0_f64;
        let mut cy = 0.0_f64;
        let mut cz = 0.0_f64;

        for (col, col_cells) in grid.iter().enumerate() {
            for (row, row_cells) in col_cells.iter().enumerate() {
                for (layer, cell) in row_cells.iter().enumerate() {
                    // Capture threshold is lower than formation — easier to join than seed.
                    let density_ok = cell.matter_density >= app_settings.galaxy_capture_density_threshold || cell.is_black_hole; // BH cells always count
                    if !density_ok {
                        continue;
                    }
                    if !self.contains(col, row, layer) {
                        continue;
                    }

                    let mass = cell.matter_density;
                    total_mass += mass;
                    cell_count += 1;
                    cx += col as f64 * mass;
                    cy += row as f64 * mass;
                    cz += layer as f64 * mass;

                    if cell.is_star && !cell.is_black_hole {
                        stellar_mass += mass;
                    }
                    if cell.is_black_hole && cell.is_supermassive {
                        smbh_mass += mass;
                    }
                }
            }
        }

        self.cell_count = cell_count;
        self.total_mass = total_mass;
        self.stellar_mass = stellar_mass;
        self.smbh_mass = smbh_mass;

        // Update mass-weighted centroid (only if we have mass to weight by)
        if total_mass > 0.0 {
            self.centroid_col = cx / total_mass;
            self.centroid_row = cy / total_mass;
            self.centroid_layer = cz / total_mass;
        }

        // Radius grows proportionally to total mass each timestep.
        // galaxy_mass_growth_rate is the fractional increase per unit mass:
        //   new_radius = old_radius + total_mass * growth_rate
        // Keeps small galaxies growing slowly, massive ones growing faster.
        let new_radius = self.radius + total_mass * app_settings.galaxy_mass_growth_rate;
        self.radius = new_radius.max(app_settings.galaxy_radius); // never shrink below seed radius
    }

    /// Apply the SMBH mass cap: any SMBH cell inside this galaxy whose
    /// matter_density exceeds the cap gets clamped.
    /// Cap = total_mass * galaxy_smbh_mass_fraction_cap
    pub fn apply_smbh_cap(&self, grid: &mut Vec<Vec<Vec<Cell>>>, app_settings: &AppSetting) {
        if self.total_mass <= 0.0 {
            return;
        }
        let cap = self.total_mass * app_settings.galaxy_smbh_mass_fraction_cap;

        for (col, col_cells) in grid.iter_mut().enumerate() {
            for (row, row_cells) in col_cells.iter_mut().enumerate() {
                for (layer, cell) in row_cells.iter_mut().enumerate() {
                    if !cell.is_black_hole || !cell.is_supermassive {
                        continue;
                    }
                    if !self.contains(col, row, layer) {
                        continue;
                    }
                    if cell.matter_density > cap {
                        cell.matter_density = cap;
                    }
                }
            }
        }
    }

    /// True if grid position (col, row, layer) falls within this galaxy's radius.
    pub fn contains(&self, col: usize, row: usize, layer: usize) -> bool {
        let dc = col as f64 - self.centroid_col;
        let dr = row as f64 - self.centroid_row;
        let dl = layer as f64 - self.centroid_layer;
        (dc * dc + dr * dr + dl * dl).sqrt() <= self.radius
    }

    /// Set galaxy_id on every cell inside this galaxy's radius.
    /// Called after update() so the centroid and radius are current.
    pub fn tag_cells(&self, grid: &mut Vec<Vec<Vec<Cell>>>) {
        let id = self.galaxy_id;
        for (col, col_cells) in grid.iter_mut().enumerate() {
            for (row, row_cells) in col_cells.iter_mut().enumerate() {
                for (layer, cell) in row_cells.iter_mut().enumerate() {
                    if self.contains(col, row, layer) {
                        cell.galaxy_id = id;
                    }
                }
            }
        }
    }
}

/// Check all active galaxy pairs for overlap. When two overlap, the
/// smaller (by total_mass) is deactivated and its mass is added to the
/// larger. Returns the indices of galaxies that were deactivated this
/// timestep so the caller can persist the change.
///
/// Overlap condition: distance between centroids < sum_of_radii * merge_overlap_fraction
pub fn process_mergers(galaxies: &mut Vec<Galaxy>, app_settings: &AppSetting) -> Vec<usize> {
    let mut deactivated: Vec<usize> = Vec::new();
    let n = galaxies.len();

    for i in 0..n {
        if !galaxies[i].is_active {
            continue;
        }
        for j in (i + 1)..n {
            if !galaxies[j].is_active {
                continue;
            }

            let dc = galaxies[i].centroid_col - galaxies[j].centroid_col;
            let dr = galaxies[i].centroid_row - galaxies[j].centroid_row;
            let dl = galaxies[i].centroid_layer - galaxies[j].centroid_layer;
            let dist = (dc * dc + dr * dr + dl * dl).sqrt();
            let threshold = (galaxies[i].radius + galaxies[j].radius) * app_settings.galaxy_merge_overlap_fraction;

            if dist < threshold {
                // Merge smaller into larger
                let (survivor, absorbed) = if galaxies[i].total_mass >= galaxies[j].total_mass { (i, j) } else { (j, i) };

                let absorbed_mass = galaxies[absorbed].total_mass;
                let absorbed_stellar = galaxies[absorbed].stellar_mass;
                let absorbed_smbh = galaxies[absorbed].smbh_mass;
                let absorbed_cells = galaxies[absorbed].cell_count;

                galaxies[survivor].total_mass += absorbed_mass;
                galaxies[survivor].stellar_mass += absorbed_stellar;
                galaxies[survivor].smbh_mass += absorbed_smbh;
                galaxies[survivor].cell_count += absorbed_cells;

                // Survivor radius grows to encompass the absorbed galaxy
                galaxies[survivor].radius = galaxies[survivor].radius.max(galaxies[absorbed].radius + dist);

                galaxies[absorbed].is_active = false;
                deactivated.push(absorbed);
            }
        }
    }

    deactivated
}

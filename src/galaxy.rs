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
    #[allow(dead_code)]
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

    /// Scan the grid for new overdensity seeds not yet claimed by any active galaxy.
    /// NOTE: O(grid × galaxy_count) — disabled in the timestep loop until spatial
    /// indexing is added. Kept here for future use.
    #[allow(dead_code)]
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
                    let claimed = existing.iter().chain(new_galaxies.iter()).any(|g| g.is_active && g.contains(col, row, layer));
                    if claimed {
                        continue;
                    }

                    *next_id -= 1;
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
                        overdensity_boost: 1.0,
                        is_active: true,
                    });
                }
            }
        }

        new_galaxies
    }

    /// True if grid position (col, row, layer) falls within this galaxy's radius.
    #[inline(always)]
    pub fn contains(&self, col: usize, row: usize, layer: usize) -> bool {
        let dc = col as f64 - self.centroid_col;
        let dr = row as f64 - self.centroid_row;
        let dl = layer as f64 - self.centroid_layer;
        (dc * dc + dr * dr + dl * dl).sqrt() <= self.radius
    }
}

/// Update all active galaxies and tag cells in a single O(grid_size) pass.
///
/// Replaces the old per-galaxy grid scans (update, apply_smbh_cap, tag_cells),
/// which were O(grid × galaxy_count) and caused stalls with large galaxy counts.
///
/// Pass 1: iterate grid once — assign each qualifying cell to the first active
///         galaxy that contains it, accumulate per-galaxy stats, tag cell.galaxy_id.
/// Pass 2: write stats back to galaxies, update centroids and radii.
/// Pass 3: iterate SMBH cells only — apply per-galaxy mass cap.
pub fn update_all_galaxies(galaxies: &mut Vec<Galaxy>, grid: &mut Vec<Vec<Vec<Cell>>>, app_settings: &AppSetting) {
    let n = galaxies.len();
    if n == 0 {
        return;
    }

    // Accumulators indexed by galaxy position in Vec.
    let mut total_mass = vec![0.0_f64; n];
    let mut stellar_mass = vec![0.0_f64; n];
    let mut smbh_mass = vec![0.0_f64; n];
    let mut cell_count = vec![0_usize; n];
    let mut cx = vec![0.0_f64; n];
    let mut cy = vec![0.0_f64; n];
    let mut cz = vec![0.0_f64; n];
    // Sum of SMBH connection strengths per galaxy — used in pass 3 to split
    // the galaxy's SMBH mass budget competitively among its SMBHs.
    let mut connection_strength_sum = vec![0.0_f64; n];

    // Pass 1: single grid scan — O(grid_size × galaxy_count) worst case but
    // exits the galaxy loop on first match, so typical cost is much lower.
    for (col_idx, col_cells) in grid.iter_mut().enumerate() {
        for (row_idx, row_cells) in col_cells.iter_mut().enumerate() {
            for (layer_idx, cell) in row_cells.iter_mut().enumerate() {
                // Reset tag — reassigned below if inside a galaxy.
                cell.galaxy_id = 0;

                let density_ok = cell.matter_density >= app_settings.galaxy_capture_density_threshold || cell.is_black_hole;
                if !density_ok {
                    continue;
                }

                for (i, galaxy) in galaxies.iter().enumerate() {
                    if !galaxy.is_active {
                        continue;
                    }
                    if galaxy.contains(col_idx, row_idx, layer_idx) {
                        cell.galaxy_id = galaxy.galaxy_id;

                        let mass = cell.matter_density;
                        total_mass[i] += mass;
                        cell_count[i] += 1;
                        cx[i] += col_idx as f64 * mass;
                        cy[i] += row_idx as f64 * mass;
                        cz[i] += layer_idx as f64 * mass;

                        if cell.is_star && !cell.is_black_hole {
                            stellar_mass[i] += mass;
                        }
                        if cell.is_black_hole && cell.is_supermassive {
                            smbh_mass[i] += mass;
                            connection_strength_sum[i] += cell.smbh_connection_strength;
                        }
                        break; // cell belongs to first matching galaxy only
                    }
                }
            }
        }
    }

    // Pass 2: write stats back, update centroids and radii.
    for (i, galaxy) in galaxies.iter_mut().enumerate() {
        if !galaxy.is_active {
            continue;
        }

        galaxy.cell_count = cell_count[i];
        galaxy.total_mass = total_mass[i];
        galaxy.stellar_mass = stellar_mass[i];
        galaxy.smbh_mass = smbh_mass[i];

        if total_mass[i] > 0.0 {
            galaxy.centroid_col = cx[i] / total_mass[i];
            galaxy.centroid_row = cy[i] / total_mass[i];
            galaxy.centroid_layer = cz[i] / total_mass[i];
        }

        // Radius grows with mass — never shrinks below seed radius.
        let new_radius = galaxy.radius + total_mass[i] * app_settings.galaxy_mass_growth_rate;
        galaxy.radius = new_radius.max(app_settings.galaxy_radius);
    }

    // Build galaxy_id -> Vec index map so pass 3 can reach the per-galaxy
    // accumulators (connection_strength_sum) by the cell's galaxy_id tag.
    let mut id_to_index: std::collections::HashMap<i64, usize> = std::collections::HashMap::new();
    for (i, galaxy) in galaxies.iter().enumerate() {
        if galaxy.is_active {
            id_to_index.insert(galaxy.galaxy_id, i);
        }
    }

    // Pass 3: competitive SMBH cap.
    //
    // The galaxy has a single SMBH mass budget = baryonic_mass * fraction.
    // That budget is split among the galaxy's SMBHs in proportion to each
    // SMBH's connection_strength relative to the galaxy's total. So:
    //   - a galaxy with one strong SMBH and many weak ones gives almost the
    //     whole budget to the strong one; the weak ones cap to near-zero.
    //   - one dominant SMBH per galaxy emerges from the heavy-tailed
    //     connection_strength distribution, not from any one-per-galaxy rule.
    //
    // Cap uses baryonic_mass (total minus SMBH) — the M-bulge reservoir,
    // independent of SMBH mass so it can't feed its own growth.
    for col_cells in grid.iter_mut() {
        for row_cells in col_cells.iter_mut() {
            for cell in row_cells.iter_mut() {
                if !cell.is_black_hole || !cell.is_supermassive || cell.galaxy_id == 0 {
                    continue;
                }
                let Some(&i) = id_to_index.get(&cell.galaxy_id) else {
                    continue;
                };

                let baryonic_mass = (total_mass[i] - smbh_mass[i]).max(0.0);
                if baryonic_mass <= 0.0 {
                    continue;
                }
                let galaxy_smbh_budget = baryonic_mass * app_settings.galaxy_smbh_mass_fraction_cap;

                // This SMBH's competitive share of the budget.
                // If the connection-strength sum is zero (degenerate), fall back
                // to an equal split is meaningless here — just cap to the full
                // budget so a lone zero-strength SMBH isn't forced to zero.
                let share = if connection_strength_sum[i] > 0.0 {
                    cell.smbh_connection_strength / connection_strength_sum[i]
                } else {
                    1.0
                };
                let cap = galaxy_smbh_budget * share;

                if cell.matter_density > cap {
                    cell.matter_density = cap;
                }
            }
        }
    }

    // Pass 4: SMBH merging within a galaxy.
    //
    // An SMBH whose competitive share falls below galaxy_smbh_stall_share_threshold
    // has lost the competition for its galaxy's mass budget. Physically, such a
    // black hole would spiral into the galaxy's dominant SMBH via dynamical
    // friction — all BHs in a galaxy eventually merge at the centre. Rather than
    // simulate the inspiral, we merge it immediately: its mass transfers to the
    // galaxy's most massive SMBH (the winner), and the stalled cell reverts to
    // ordinary matter (is_black_hole and is_supermassive cleared).
    //
    // Done in two sweeps to satisfy the borrow checker:
    //   4a. Find each galaxy's winner coordinates and accumulate stalled mass.
    //   4b. Clear stalled cells; then add absorbed mass to each winner.

    // Winner tracking per galaxy index: (mass, col, row, layer)
    let mut winner: Vec<Option<(f64, usize, usize, usize)>> = vec![None; n];
    let mut absorbed_mass = vec![0.0_f64; n];

    // 4a: identify winners and stalled mass. Read-only scan.
    for (col_idx, col_cells) in grid.iter().enumerate() {
        for (row_idx, row_cells) in col_cells.iter().enumerate() {
            for (layer_idx, cell) in row_cells.iter().enumerate() {
                if !cell.is_black_hole || !cell.is_supermassive || cell.galaxy_id == 0 {
                    continue;
                }
                let Some(&i) = id_to_index.get(&cell.galaxy_id) else {
                    continue;
                };

                // Track the most massive SMBH in this galaxy as the winner.
                let is_new_winner = match winner[i] {
                    None => true,
                    Some((best_mass, _, _, _)) => cell.matter_density > best_mass,
                };
                if is_new_winner {
                    winner[i] = Some((cell.matter_density, col_idx, row_idx, layer_idx));
                }
            }
        }
    }

    // 4b: clear stalled SMBHs and accumulate their mass to the galaxy total.
    for (col_idx, col_cells) in grid.iter_mut().enumerate() {
        for (row_idx, row_cells) in col_cells.iter_mut().enumerate() {
            for (layer_idx, cell) in row_cells.iter_mut().enumerate() {
                if !cell.is_black_hole || !cell.is_supermassive || cell.galaxy_id == 0 {
                    continue;
                }
                let Some(&i) = id_to_index.get(&cell.galaxy_id) else {
                    continue;
                };

                // Don't merge the winner into itself.
                if let Some((_, wc, wr, wl)) = winner[i] {
                    if wc == col_idx && wr == row_idx && wl == layer_idx {
                        continue;
                    }
                }

                let share = if connection_strength_sum[i] > 0.0 {
                    cell.smbh_connection_strength / connection_strength_sum[i]
                } else {
                    1.0
                };

                if share < app_settings.galaxy_smbh_stall_share_threshold {
                    // Stalled — merge into winner. Transfer mass, revert cell.
                    absorbed_mass[i] += cell.matter_density;
                    cell.is_black_hole = false;
                    cell.is_supermassive = false;
                    cell.smbh_connection_strength = 0.0;
                    cell.black_hole_id = None;
                    cell.matter_density = 0.0; // mass moved to winner, not left behind
                }
            }
        }
    }

    // 4b (cont.): deposit absorbed mass into each galaxy's winner cell.
    for (i, w) in winner.iter().enumerate() {
        if let Some((_, wc, wr, wl)) = *w {
            if absorbed_mass[i] > 0.0 {
                grid[wc][wr][wl].matter_density += absorbed_mass[i];
            }
        }
    }
}

/// Check all active galaxy pairs for overlap. When two overlap, the
/// smaller (by total_mass) is deactivated and its mass absorbed by the larger.
/// Returns indices of galaxies deactivated this timestep.
///
/// Overlap condition: centroid distance < (r_i + r_j) * merge_overlap_fraction
#[allow(dead_code)]
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
                let (survivor, absorbed) = if galaxies[i].total_mass >= galaxies[j].total_mass { (i, j) } else { (j, i) };

                let absorbed_mass = galaxies[absorbed].total_mass;
                let absorbed_stellar = galaxies[absorbed].stellar_mass;
                let absorbed_smbh = galaxies[absorbed].smbh_mass;
                let absorbed_cells = galaxies[absorbed].cell_count;

                galaxies[survivor].total_mass += absorbed_mass;
                galaxies[survivor].stellar_mass += absorbed_stellar;
                galaxies[survivor].smbh_mass += absorbed_smbh;
                galaxies[survivor].cell_count += absorbed_cells;

                // Survivor radius expands to encompass absorbed galaxy.
                galaxies[survivor].radius = galaxies[survivor].radius.max(galaxies[absorbed].radius + dist);

                galaxies[absorbed].is_active = false;
                deactivated.push(absorbed);
            }
        }
    }

    deactivated
}

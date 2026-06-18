use crate::database::app_settings::AppSetting;
use crate::database::entities::cell::Cell;
use std::collections::HashMap;

/// A galaxy: a gravitationally-bound (here, friends-of-friends linked) collection
/// of matter, found fresh from the density field every timestep after inflation.
///
/// Nothing about a galaxy is seeded or persisted across timesteps except its
/// *identity* (`galaxy_id` and `formed_timestep`), which is carried forward by
/// overlap-matching in `find_galaxies`. Membership, mass, centroid, and extent
/// are always re-derived from the current density field — the galaxy at timestep
/// t is a pure function of the grid at timestep t. Physics is memoryless;
/// identity is a thin bookkeeping layer on top.
#[derive(Debug, Clone)]
pub struct Galaxy {
    pub galaxy_id: i64,
    pub run_id: i64,
    pub formed_timestep: usize,

    /// Centroid in grid coordinates, derived from member cells.
    pub centroid_col: f64,
    pub centroid_row: f64,
    pub centroid_layer: f64,

    /// Reporting extent: max member distance from centroid. Derived, not a gate.
    pub radius: f64,
    pub total_mass: f64,
    pub stellar_mass: f64,
    pub smbh_mass: f64,
    pub cell_count: usize,

    /// Always true for a found galaxy; retained for DB-schema compatibility and
    /// so a dissolved/merged galaxy can be marked inactive when persisted.
    pub is_active: bool,
}

impl Galaxy {
    /// Stamp run_id onto a galaxy list. Retained for call-site compatibility;
    /// with dynamic finding the list is usually empty at the call point, but
    /// find_galaxies also stamps run_id directly, so this is belt-and-suspenders.
    pub fn assign_run_id(galaxies: &mut [Galaxy], run_id: i64) {
        for g in galaxies.iter_mut() {
            g.run_id = run_id;
        }
    }
}

/// Internal: a connected component discovered by the FoF pass, before it is
/// matched to a prior galaxy's identity.
struct Component {
    cells: Vec<(usize, usize, usize)>,
    total_mass: f64,
    stellar_mass: f64,
    smbh_mass: f64,
    centroid_col: f64,
    centroid_row: f64,
    centroid_layer: f64,
    radius: f64,
}

/// Union-find (disjoint set) over a flattened grid index space.
struct UnionFind {
    parent: Vec<usize>,
    rank: Vec<u8>,
}

impl UnionFind {
    fn new(n: usize) -> Self {
        UnionFind {
            parent: (0..n).collect(),
            rank: vec![0; n],
        }
    }

    fn find(&mut self, x: usize) -> usize {
        // Path-halving find.
        let mut x = x;
        while self.parent[x] != x {
            self.parent[x] = self.parent[self.parent[x]];
            x = self.parent[x];
        }
        x
    }

    fn union(&mut self, a: usize, b: usize) {
        let ra = self.find(a);
        let rb = self.find(b);
        if ra == rb {
            return;
        }
        if self.rank[ra] < self.rank[rb] {
            self.parent[ra] = rb;
        } else if self.rank[ra] > self.rank[rb] {
            self.parent[rb] = ra;
        } else {
            self.parent[rb] = ra;
            self.rank[ra] += 1;
        }
    }
}

/// Find galaxies in the current density field via friends-of-friends, match them
/// to the previous timestep's galaxies to preserve identity, and tag each member
/// cell's `galaxy_id`. Replaces the old seed/update/merge pipeline entirely.
///
/// Steps:
///   1. FoF labeling: union neighbouring cells whose matter_density is above the
///      linking threshold (6-connectivity). O(grid) via union-find.
///   2. Build components; keep those with at least `galaxy_min_cells` cells.
///   3. Identity matching: each component inherits the galaxy_id of the prior
///      galaxy it shares the most cells with. Unmatched components are new
///      galaxies. Merge-only: if two prior galaxies map to one component, the
///      larger lends its id (topological merge — two regions became one).
///   4. Tag member cells with the resolved galaxy_id; cells in no galaxy get 0.
///
/// `prev_galaxies` is last timestep's result (for identity). `prev_membership`
/// maps a (col,row,layer) to the galaxy_id it held last timestep, used for
/// overlap matching. Returns the new galaxy list; `next_id` advances for any
/// newly-formed galaxies.
pub fn find_galaxies(grid: &mut [Vec<Vec<Cell>>], prev_membership: &HashMap<(usize, usize, usize), i64>, app_settings: &AppSetting, timestep: usize, run_id: i64, next_id: &mut i64) -> Vec<Galaxy> {
    let height = grid.len();
    let width = if height > 0 { grid[0].len() } else { 0 };
    let depth = if width > 0 { grid[0][0].len() } else { 0 };
    let n = height * width * depth;
    if n == 0 {
        return Vec::new();
    }

    let idx = |c: usize, r: usize, l: usize| -> usize { (c * width + r) * depth + l };

    let threshold = app_settings.galaxy_fof_density_threshold;

    // --- Step 1: FoF union-find over above-threshold cells (6-connectivity) ---
    let mut uf = UnionFind::new(n);
    // Mark which cells are galaxy material so we only build components from them.
    let mut is_material = vec![false; n];

    // A cell is galaxy material (a linking node) if it is a black hole (the
    // gravitational anchor of a galaxy — always part of it) OR ordinary matter
    // above the FoF linking threshold. BH cells must link: a central SMBH should
    // bridge the dense region around it into one galaxy, not split it. (Their
    // matter_density is a sentinel and not meaningful for a density test, so
    // BH-ness itself is the qualifier.)
    let is_link = |cell: &Cell| cell.is_black_hole || cell.matter_density >= threshold;

    for c in 0..height {
        for r in 0..width {
            for l in 0..depth {
                if !is_link(&grid[c][r][l]) {
                    continue;
                }
                is_material[idx(c, r, l)] = true;

                // Link to the three lower-index face neighbours (avoids double work).
                if c > 0 && is_link(&grid[c - 1][r][l]) {
                    uf.union(idx(c, r, l), idx(c - 1, r, l));
                }
                if r > 0 && is_link(&grid[c][r - 1][l]) {
                    uf.union(idx(c, r, l), idx(c, r - 1, l));
                }
                if l > 0 && is_link(&grid[c][r][l - 1]) {
                    uf.union(idx(c, r, l), idx(c, r, l - 1));
                }
            }
        }
    }

    // --- Step 2: gather components keyed by union-find root ---
    let mut comps: HashMap<usize, Component> = HashMap::new();
    for c in 0..height {
        for r in 0..width {
            for l in 0..depth {
                let flat = idx(c, r, l);
                if !is_material[flat] {
                    continue;
                }
                let root = uf.find(flat);
                let cell = &grid[c][r][l];
                let entry = comps.entry(root).or_insert_with(|| Component {
                    cells: Vec::new(),
                    total_mass: 0.0,
                    stellar_mass: 0.0,
                    smbh_mass: 0.0,
                    centroid_col: 0.0,
                    centroid_row: 0.0,
                    centroid_layer: 0.0,
                    radius: 0.0,
                });
                entry.cells.push((c, r, l));
                // Black-hole cells carry a sentinel matter_density; excluding them
                // from total_mass keeps the galaxy's baryonic mass meaningful.
                // Their mass is tracked separately as smbh_mass.
                if cell.is_black_hole {
                    if cell.is_supermassive {
                        entry.smbh_mass += cell.matter_density;
                    }
                } else {
                    entry.total_mass += cell.matter_density;
                    if cell.is_star {
                        entry.stellar_mass += cell.matter_density;
                    }
                }
                // Accumulate centroid as running sum; divided after.
                entry.centroid_col += c as f64;
                entry.centroid_row += r as f64;
                entry.centroid_layer += l as f64;
            }
        }
    }

    // Finalize centroids/radius, drop sub-threshold-size components.
    let min_cells = app_settings.galaxy_min_cells;
    let mut components: Vec<Component> = comps
        .into_values()
        .filter(|comp| comp.cells.len() >= min_cells)
        .map(|mut comp| {
            let count = comp.cells.len() as f64;
            comp.centroid_col /= count;
            comp.centroid_row /= count;
            comp.centroid_layer /= count;
            let mut max_r2 = 0.0_f64;
            for &(c, r, l) in &comp.cells {
                let dc = c as f64 - comp.centroid_col;
                let dr = r as f64 - comp.centroid_row;
                let dl = l as f64 - comp.centroid_layer;
                let r2 = dc * dc + dr * dr + dl * dl;
                if r2 > max_r2 {
                    max_r2 = r2;
                }
            }
            comp.radius = max_r2.sqrt();
            comp
        })
        .collect();

    // --- Step 3: identity matching by member overlap ---
    // For each component, count how many of its cells belonged to each prior
    // galaxy_id last timestep. The prior id with the most shared cells wins,
    // provided the overlap meets the minimum fraction. Merge-only behaviour
    // falls out naturally: if two prior galaxies both overlap one component,
    // only the larger-overlap one lends its id; the other simply isn't carried
    // forward (its matter is now part of this single merged component).
    let min_overlap = app_settings.galaxy_match_min_overlap;
    let mut galaxies: Vec<Galaxy> = Vec::with_capacity(components.len());
    // Track which prior ids have already been claimed this step so two components
    // can't both inherit the same id (a split — disallowed; the later/smaller
    // component becomes a new galaxy instead).
    let mut claimed_ids: std::collections::HashSet<i64> = std::collections::HashSet::new();

    // Sort components by mass descending so the largest claims contested ids first
    // (consistent with "larger galaxy keeps its identity through a merge").
    components.sort_by(|a, b| b.total_mass.partial_cmp(&a.total_mass).unwrap_or(std::cmp::Ordering::Equal));

    for comp in &components {
        // Tally overlap with prior galaxy ids.
        let mut overlap: HashMap<i64, usize> = HashMap::new();
        for &(c, r, l) in &comp.cells {
            if let Some(&pid) = prev_membership.get(&(c, r, l)) {
                if pid > 0 {
                    *overlap.entry(pid).or_insert(0) += 1;
                }
            }
        }

        // Pick the best unclaimed prior id meeting the overlap fraction.
        let comp_cells = comp.cells.len() as f64;
        let mut best_id: Option<i64> = None;
        let mut best_count = 0usize;
        for (&pid, &count) in &overlap {
            if claimed_ids.contains(&pid) {
                continue;
            }
            let frac = count as f64 / comp_cells;
            if frac >= min_overlap && count > best_count {
                best_count = count;
                best_id = Some(pid);
            }
        }

        let resolved_id = match best_id {
            Some(pid) => pid,
            None => {
                *next_id += 1;
                *next_id
            }
        };

        // formed_timestep: identity is carried by galaxy_id, not birth step. We
        // attribute the current step here. (Thread a HashMap<id, formed_timestep>
        // alongside prev_membership later if exact birth history is needed.)
        let formed = timestep;

        claimed_ids.insert(resolved_id);

        galaxies.push(Galaxy {
            galaxy_id: resolved_id,
            run_id,
            formed_timestep: formed,
            centroid_col: comp.centroid_col,
            centroid_row: comp.centroid_row,
            centroid_layer: comp.centroid_layer,
            radius: comp.radius,
            total_mass: comp.total_mass,
            stellar_mass: comp.stellar_mass,
            smbh_mass: comp.smbh_mass,
            cell_count: comp.cells.len(),
            is_active: true,
        });
    }

    // --- Step 4: tag member cells with resolved galaxy_id; clear the rest ---
    // First clear all tags (cheap, single pass).
    for c in 0..height {
        for r in 0..width {
            for l in 0..depth {
                grid[c][r][l].galaxy_id = 0;
            }
        }
    }
    // Then stamp each galaxy's members. Components and galaxies are in the same
    // order (galaxies built by iterating components), so re-zip them.
    for (gi, comp) in components.iter().enumerate() {
        let gid = galaxies[gi].galaxy_id;
        for &(c, r, l) in &comp.cells {
            grid[c][r][l].galaxy_id = gid;
        }
    }

    galaxies
}

/// Build the membership map (cell -> galaxy_id) for the current galaxies, to be
/// passed into next timestep's `find_galaxies` for identity matching.
pub fn build_membership(grid: &[Vec<Vec<Cell>>]) -> HashMap<(usize, usize, usize), i64> {
    let mut m = HashMap::new();
    for (c, col_cells) in grid.iter().enumerate() {
        for (r, row_cells) in col_cells.iter().enumerate() {
            for (l, cell) in row_cells.iter().enumerate() {
                if cell.galaxy_id > 0 {
                    m.insert((c, r, l), cell.galaxy_id);
                }
            }
        }
    }
    m
}

/// Competitive SMBH cap and intra-galaxy SMBH merging.
///
/// Runs after `find_galaxies` has tagged cell.galaxy_id. Each galaxy has a single
/// SMBH mass budget (a fraction of its baryonic mass) split among its SMBHs in
/// proportion to connection strength; SMBHs whose share falls below the stall
/// threshold merge into the galaxy's dominant SMBH. See decisions.md for the full
/// reasoning. This is unchanged from the seeded-galaxy implementation — it keys
/// purely off galaxy_id membership, so it works identically with FoF galaxies.
pub fn apply_smbh_competition(galaxies: &[Galaxy], grid: &mut [Vec<Vec<Cell>>], app_settings: &AppSetting) {
    let n = galaxies.len();
    if n == 0 {
        return;
    }

    // Per-galaxy accumulators, indexed by position in `galaxies`.
    let mut total_mass = vec![0.0_f64; n];
    let mut smbh_mass = vec![0.0_f64; n];
    let mut connection_strength_sum = vec![0.0_f64; n];

    let mut id_to_index: HashMap<i64, usize> = HashMap::new();
    for (i, g) in galaxies.iter().enumerate() {
        id_to_index.insert(g.galaxy_id, i);
        total_mass[i] = g.total_mass;
    }

    // Accumulate SMBH mass and connection strength per galaxy.
    for col_cells in grid.iter() {
        for row_cells in col_cells.iter() {
            for cell in row_cells.iter() {
                if cell.is_black_hole && cell.is_supermassive && cell.galaxy_id != 0 {
                    if let Some(&i) = id_to_index.get(&cell.galaxy_id) {
                        smbh_mass[i] += cell.matter_density;
                        connection_strength_sum[i] += cell.smbh_connection_strength;
                    }
                }
            }
        }
    }

    // Pass 3: competitive cap.
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

    // Pass 4: intra-galaxy SMBH merging.
    let mut winner: Vec<Option<(f64, usize, usize, usize)>> = vec![None; n];
    let mut absorbed_mass = vec![0.0_f64; n];

    for (col_idx, col_cells) in grid.iter().enumerate() {
        for (row_idx, row_cells) in col_cells.iter().enumerate() {
            for (layer_idx, cell) in row_cells.iter().enumerate() {
                if !cell.is_black_hole || !cell.is_supermassive || cell.galaxy_id == 0 {
                    continue;
                }
                let Some(&i) = id_to_index.get(&cell.galaxy_id) else {
                    continue;
                };
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

    for (col_idx, col_cells) in grid.iter_mut().enumerate() {
        for (row_idx, row_cells) in col_cells.iter_mut().enumerate() {
            for (layer_idx, cell) in row_cells.iter_mut().enumerate() {
                if !cell.is_black_hole || !cell.is_supermassive || cell.galaxy_id == 0 {
                    continue;
                }
                let Some(&i) = id_to_index.get(&cell.galaxy_id) else {
                    continue;
                };
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
                    absorbed_mass[i] += cell.matter_density;
                    cell.is_black_hole = false;
                    cell.is_supermassive = false;
                    cell.smbh_connection_strength = 0.0;
                    cell.black_hole_id = None;
                    cell.matter_density = 0.0;
                }
            }
        }
    }

    for (i, w) in winner.iter().enumerate() {
        if let Some((_, wc, wr, wl)) = *w {
            if absorbed_mass[i] > 0.0 {
                grid[wc][wr][wl].matter_density += absorbed_mass[i];
            }
        }
    }
}

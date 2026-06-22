use crate::database::app_settings::AppSetting;
use crate::database::db_provider::DbProvider;
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
/// overlap matching. Returns the new galaxy list. Newly-born galaxies (no overlap
/// match) get a NEGATIVE sentinel id (-1, -2, ...). The caller persists them via
/// insert_galaxies, which swaps each sentinel for a real positive DB rowid, then
/// re-tags the grid before build_membership runs. The galaxy table's autoincrement
/// is the single source of truth for ids — there is no in-memory counter to seed
/// or keep in sync across runs.
pub fn find_galaxies(grid: &mut [Vec<Vec<Cell>>], prev_membership: &HashMap<(usize, usize, usize), i64>, app_settings: &AppSetting, timestep: usize, run_id: i64) -> Vec<Galaxy> {
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

                // Link to the three lower-index face neighbors (avoids double work).
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
    // provided the overlap meets the minimum fraction. Merge-only behavior
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

    // Newly-born galaxies get a negative sentinel id, assigned here and replaced
    // with a real positive DB rowid by the caller's insert_galaxies pass. Negative
    // ids never collide with positive DB RowIds, so a sentinel that leaks into the
    // DB or membership map is an obvious, fail-loud bug.
    let mut next_sentinel: i64 = -1;

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
                let id = next_sentinel;
                next_sentinel -= 1;
                id
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

/// Persist this timestep's galaxies to the DB and finalize their ids.
///
/// Must run AFTER find_galaxies (which assigns negative sentinel ids to newborns
/// and tags member cells with them) and BEFORE build_membership (which only keeps
/// positive ids, so sentinels must be resolved first or identity would be lost).
///
/// Steps:
///   1. Count SMBHs per galaxy from the grid (single pass over BH cells).
///   2. Insert newborns (negative id) in one transaction; the DB stamps real
///      positive Row Ids back onto the structs.
///   3. Re-tag grid cells that held a sentinel with the real id (single pass).
///   4. Snapshot every active galaxy into galaxy_timestep (one transaction).
///   5. Deactivate prior ids that no component carried forward (merged/dissolved).
///
/// `prev_ids` is the set of positive galaxy ids that existed last timestep, used
/// to detect which galaxies vanished this step. Pass the keys/values of the prior
/// membership map (deduplicated) — or simply the prior galaxy list's ids.
pub fn persist_galaxies(db: &mut dyn DbProvider, galaxies: &mut [Galaxy], grid: &mut [Vec<Vec<Cell>>], prev_ids: &std::collections::HashSet<i64>, timestep: usize) -> Result<(), rusqlite::Error> {
    // --- Step 1: per-galaxy SMBH counts, indexed to match `galaxies` ---
    let mut id_to_index: HashMap<i64, usize> = HashMap::new();
    for (i, g) in galaxies.iter().enumerate() {
        id_to_index.insert(g.galaxy_id, i);
    }
    let mut smbh_counts = vec![0i64; galaxies.len()];
    for col_cells in grid.iter() {
        for row_cells in col_cells.iter() {
            for cell in row_cells.iter() {
                if cell.is_black_hole && cell.is_supermassive && cell.galaxy_id != 0 {
                    if let Some(&i) = id_to_index.get(&cell.galaxy_id) {
                        smbh_counts[i] += 1;
                    }
                }
            }
        }
    }

    // --- Step 2: insert newborns (negative sentinel id), capture sentinel->real ---
    // Record each newborn's sentinel before insert so we can remap grid tags after.
    let mut sentinel_to_real: HashMap<i64, i64> = HashMap::new();
    {
        let mut newborn_refs: Vec<&mut Galaxy> = galaxies.iter_mut().filter(|g| g.galaxy_id < 0).collect();
        // Stash sentinels in input order; insert_galaxies preserves order and stamps
        // real ids back, so we can zip sentinel -> real afterwards.
        let sentinels: Vec<i64> = newborn_refs.iter().map(|g| g.galaxy_id).collect();
        db.insert_galaxies(&mut newborn_refs)?;
        for (sentinel, g) in sentinels.iter().zip(newborn_refs.iter()) {
            sentinel_to_real.insert(*sentinel, g.galaxy_id);
        }
    }

    // --- Step 3: re-tag grid cells that still carry a sentinel ---
    if !sentinel_to_real.is_empty() {
        for col_cells in grid.iter_mut() {
            for row_cells in col_cells.iter_mut() {
                for cell in row_cells.iter_mut() {
                    if cell.galaxy_id < 0 {
                        if let Some(&real) = sentinel_to_real.get(&cell.galaxy_id) {
                            cell.galaxy_id = real;
                        }
                    }
                }
            }
        }
    }

    // --- Step 4: snapshot every active galaxy ---
    db.record_galaxy_timesteps(galaxies, &smbh_counts, timestep)?;

    // --- Step 5: deactivate prior ids not carried forward this step ---
    let current_ids: std::collections::HashSet<i64> = galaxies.iter().map(|g| g.galaxy_id).collect();
    let vanished: Vec<i64> = prev_ids.iter().filter(|id| !current_ids.contains(id)).copied().collect();
    if !vanished.is_empty() {
        db.deactivate_galaxies(&vanished)?;
    }

    Ok(())
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
    // Accumulated per galaxy but no longer used in the cap denominator (see the
    // double-subtraction fix below). Kept for potential future diagnostics.
    let mut _smbh_mass = vec![0.0_f64; n];
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
                        _smbh_mass[i] += cell.matter_density;
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
                // total_mass[i] is ALREADY baryonic: find_galaxies accumulates it
                // from non-BH cells only (BH mass goes to smbh_mass separately).
                // Subtracting smbh_mass here would be a double-subtraction that
                // drives the cap denominator to zero as an SMBH grows — removing
                // its own cap and producing runaway growth. The budget must be
                // independent of the thing being capped.
                let baryonic_mass = total_mass[i].max(0.0);
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
                // The dominant (most massive) SMBH in this galaxy is never absorbed.
                let Some((winner_mass, wc, wr, wl)) = winner[i] else {
                    continue;
                };
                if wc == col_idx && wr == row_idx && wl == layer_idx {
                    continue;
                }
                // Mass-based dominance: absorb this SMBH if its mass is below the
                // configured fraction of the dominant SMBH's mass. Comparable-mass
                // pairs (post-merger duals) survive until one pulls ahead, giving
                // emergent ≈one-dominant-per-galaxy with rare transient duals.
                // Winner-selection and absorption now key off the SAME quantity
                // (mass), unlike the prior connection-strength-share criterion,
                // which let many comparable-strength SMBHs all survive.
                let dominance_floor = winner_mass * app_settings.galaxy_smbh_dominance_threshold;
                if cell.matter_density < dominance_floor {
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

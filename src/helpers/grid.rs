use crate::AppSetting;
use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::galaxy::place_galaxies;
use crate::initial_geometry::InitialGeometry;
use indicatif::ProgressBar;
use rand::Rng;

pub fn populate_grid(
    geometry: &InitialGeometry,
    grid: &mut Vec<Vec<Vec<Cell>>>,
    db: &dyn DbProvider, // only used for Custom
) -> rusqlite::Result<()> {
    let depth = grid.len();
    let height = if depth > 0 { grid[0].len() } else { 0 };
    let width = if height > 0 { grid[0][0].len() } else { 0 };

    let mut rng = rand::thread_rng();

    match geometry {
        InitialGeometry::Uniform { density } => {
            for layer in grid.iter_mut() {
                for row in layer.iter_mut() {
                    for cell in row.iter_mut() {
                        cell.matter_density = *density;
                    }
                }
            }
        }

        InitialGeometry::GaussianBlobs {
            count,
            peak_density,
            sigma_min,
            sigma_max,
        } => {
            // Pick N random centers + sigmas, then add gaussian contributions per cell
            let blobs: Vec<(f64, f64, f64, f64)> = (0..*count)
                .map(|_| {
                    let cx = rng.gen_range(0.0..width as f64);
                    let cy = rng.gen_range(0.0..height as f64);
                    let cz = rng.gen_range(0.0..depth as f64);
                    let sigma = rng.gen_range(*sigma_min..*sigma_max);
                    (cx, cy, cz, sigma)
                })
                .collect();

            for (z, layer) in grid.iter_mut().enumerate() {
                for (y, row) in layer.iter_mut().enumerate() {
                    for (x, cell) in row.iter_mut().enumerate() {
                        let mut sum = 0.0;
                        for &(cx, cy, cz, sigma) in &blobs {
                            let dx = x as f64 - cx;
                            let dy = y as f64 - cy;
                            let dz = z as f64 - cz;
                            let r2 = dx * dx + dy * dy + dz * dz;
                            sum += peak_density * (-r2 / (2.0 * sigma * sigma)).exp();
                        }
                        cell.matter_density = sum;
                    }
                }
            }
        }

        InitialGeometry::Perlin { octaves, frequency, amplitude, seed } => {
            use noise::{NoiseFn, Perlin};
            let perlin = Perlin::new(*seed);

            for (z, layer) in grid.iter_mut().enumerate() {
                for (y, row) in layer.iter_mut().enumerate() {
                    for (x, cell) in row.iter_mut().enumerate() {
                        let mut value = 0.0;
                        let mut freq = *frequency;
                        let mut amp = *amplitude;
                        for _ in 0..*octaves {
                            value += perlin.get([x as f64 * freq, y as f64 * freq, z as f64 * freq]) * amp;
                            freq *= 2.0;
                            amp *= 0.5;
                        }
                        // Perlin returns ~[-1, 1]; shift to non-negative density
                        cell.matter_density = (value + 1.0).max(0.0);
                    }
                }
            }
        }

        InitialGeometry::Custom => {
            // Default to 0 first
            for layer in grid.iter_mut() {
                for row in layer.iter_mut() {
                    for cell in row.iter_mut() {
                        cell.matter_density = 0.0;
                    }
                }
            }

            let rows = db.load_custom_density()?;
            for (col, row, layer, density) in rows {
                if layer < depth && row < height && col < width {
                    grid[layer][row][col].matter_density = density;
                }
            }
        }
    }

    return Ok(());
}

pub fn seed_initial_curvature(grid: &mut Vec<Vec<Vec<Cell>>>, settings: &AppSetting, db: &mut dyn DbProvider) -> Vec<crate::galaxy::Galaxy> {
    let progress_bar: ProgressBar = ProgressBar::new((settings.inf_grid_height * settings.inf_grid_width * settings.inf_grid_depth) as u64);
    let mut rng = rand::thread_rng();

    // Place galaxy regions first so we can boost curvature inside them below.
    let galaxies = place_galaxies(
        settings.inf_grid_height,
        settings.inf_grid_width,
        settings.inf_grid_depth,
        settings.galaxy_count,
        settings.galaxy_radius,
        settings.galaxy_overdensity, // stored on Galaxy for use by apply_galaxy_overdensity
        &mut rng,
    );

    for height in 0..settings.inf_grid_height {
        for width in 0..settings.inf_grid_width {
            for depth in 0..settings.inf_grid_depth {
                let cell = &mut grid[height][width][depth];
                progress_bar.inc(1);
                cell.layer = depth;
                cell.position = db.get_or_insert_cell_position(width, height);
                cell.curvature = rng.gen_range(0.0..0.1);

                // Cells inside a galaxy region get a curvature bonus — raises the
                // local floor so SMBH formation threshold is more reachable there.
                if galaxies.iter().any(|g| g.contains(height, width, depth)) {
                    cell.curvature += settings.galaxy_curvature_boost;
                }
            }
        }
    }

    progress_bar.finish_with_message("Seeding simulation complete.");
    return galaxies;
}

// ── ADD this new function anywhere in the file after populate_grid: ───────────────────────

/// Apply galaxy overdensity boosts to cells that fall inside a galaxy region.
/// Called from create_data.rs immediately after populate_grid, as a separate pass
/// so populate_grid stays single-responsibility (base geometry only).
pub fn apply_galaxy_overdensity(grid: &mut Vec<Vec<Vec<Cell>>>, galaxies: &[crate::galaxy::Galaxy], settings: &AppSetting) {
    for height in 0..settings.inf_grid_height {
        for width in 0..settings.inf_grid_width {
            for depth in 0..settings.inf_grid_depth {
                if galaxies.iter().any(|g| g.contains(height, width, depth)) {
                    // Boost matter density inside galaxy regions.
                    // Multiplicative so it scales with whatever the base geometry produced.
                    grid[height][width][depth].matter_density *= galaxies.iter().find(|g| g.contains(height, width, depth)).map(|g| g.overdensity_boost).unwrap_or(1.0);
                }
            }
        }
    }
}

use crate::AppSetting;
use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
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

        InitialGeometry::BulletCluster { sigma, peak_density, separation } => {
            // One Gaussian clump at box center (separation == 0, formation), or a
            // colliding PAIR offset +/- separation from center along the WIDTH axis
            // (separation > 0). Only the baryon overdensities are seeded; the dimple
            // halos are EMERGENT (rips), never painted in.
            //
            // AXIS CONVENTION: create_data allocates grid[height][width][depth]
            // (outer = height, middle = width, inner = depth). The locals named
            // depth/height/width above are SWAPPED relative to that allocation, so
            // index explicitly here. Collision axis = WIDTH = the middle index.
            //
            // PERIODIC-STALL NOTE: two equal clumps at exactly half-box separation
            // feel equal pull both ways and never fall together. Keep
            // separation < n_w/4 so the pair (2*separation apart) stays under the
            // half-box stall and falls together the short way.
            let n_h = grid.len();
            let n_w = if n_h > 0 { grid[0].len() } else { 0 };
            let n_d = if n_w > 0 { grid[0][0].len() } else { 0 };
            let (ch, cd) = (n_h as f64 / 2.0, n_d as f64 / 2.0);
            let cw = n_w as f64 / 2.0;
            let centers: Vec<f64> = if *separation == 0 { vec![cw] } else { vec![cw - *separation as f64, cw + *separation as f64] };
            let two_sigma2 = 2.0 * sigma * sigma;
            for h in 0..n_h {
                for w in 0..n_w {
                    for d in 0..n_d {
                        let dh = h as f64 - ch;
                        let dd = d as f64 - cd;
                        let mut sum = 0.0;
                        for &cwc in &centers {
                            let dw = w as f64 - cwc;
                            let r2 = dh * dh + dw * dw + dd * dd;
                            sum += peak_density * (-r2 / two_sigma2).exp();
                        }
                        grid[h][w][d].matter_density = sum;
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

    // Galaxies are no longer seeded here. They emerge from the density field via
    // friends-of-friends after inflation (see galaxy::find_galaxies). The initial
    // curvature is the broad-spectrum primordial fluctuation field — random per
    // cell — out of which structure later condenses. No discrete galaxy lumps.
    for height in 0..settings.inf_grid_height {
        for width in 0..settings.inf_grid_width {
            for depth in 0..settings.inf_grid_depth {
                let cell = &mut grid[height][width][depth];
                progress_bar.inc(1);
                cell.layer = depth;
                let position = db.get_or_insert_cell_position(width, height);
                cell.cell_position_id = position.cell_position_id;
                cell.curvature = rng.gen_range(0.0..0.1);
            }
        }
    }

    progress_bar.finish_with_message("Seeding simulation complete.");
    // Return empty: galaxies are found dynamically each post-inflation timestep.
    Vec::new()
}

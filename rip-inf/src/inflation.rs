use csv::Writer;
use rand::Rng;
use rip_core::cell::Cell;
use rip_core::helpers::create_gzip_writer;
use std::f64;

const GRID_WIDTH: usize = 64;
const GRID_HEIGHT: usize = 64;
const GRID_DEPTH: usize = 64;
const NUM_TIMESTEPS: usize = 100;

const CURVATURE_THRESHOLD: f64 = 0.2;
const COLLAPSE_DENSITY_THRESHOLD: f64 = 0.005;

fn seed_initial_curvature(grid: &mut Vec<Vec<Vec<Cell>>>) {
    let mut rng = rand::thread_rng();
    for col in 0..GRID_WIDTH {
        for row in 0..GRID_HEIGHT {
            for layer in 0..GRID_DEPTH {
                let cell = &mut grid[col][row][layer];
                cell.col = col;
                cell.row = row;
                cell.layer = layer;
                cell.curvature = rng.gen_range(0.0..0.1);
                cell.assign_neighbors(GRID_WIDTH);
            }
        }
    }
}

fn stretch_curvature(grid: &mut Vec<Vec<Vec<Cell>>>, axis: &str) {
    for x in 0..GRID_WIDTH {
        for y in 0..GRID_HEIGHT {
            for z in 0..GRID_DEPTH {
                let factor: f64 = match axis {
                    "col" => 1.0 + (x as f64),
                    "row" => 1.0 + (y as f64),
                    "layer" => 1.0 + (z as f64),
                    _ => 1.0,
                };
                grid[x][y][z].curvature *= factor;
            }
        }
    }
}

fn smooth_density(grid: &Vec<Vec<Vec<f64>>>) -> Vec<Vec<Vec<f64>>> {
    let mut result = vec![vec![vec![0.0; GRID_DEPTH]; GRID_HEIGHT]; GRID_WIDTH];
    let radius = 1;

    for x in 0..GRID_WIDTH {
        for y in 0..GRID_HEIGHT {
            for z in 0..GRID_DEPTH {
                let mut total = 0.0;
                let mut count = 0;
                for dx in -radius..=radius {
                    for dy in -radius..=radius {
                        for dz in -radius..=radius {
                            let nx = x as isize + dx;
                            let ny = y as isize + dy;
                            let nz = z as isize + dz;
                            if nx >= 0
                                && ny >= 0
                                && nz >= 0
                                && nx < GRID_WIDTH as isize
                                && ny < GRID_HEIGHT as isize
                                && nz < GRID_DEPTH as isize
                            {
                                total += grid[nx as usize][ny as usize][nz as usize];
                                count += 1;
                            }
                        }
                    }
                }
                result[x][y][z] = total / count as f64;
            }
        }
    }
    result
}

pub fn run() {
    let writer = create_gzip_writer("data/inflation.csv.gz");
    let mut csv_writer = Writer::from_writer(writer);
    // "timestep,col,row,layer,curvature,matter_density,is_black_hole,rip_strength,matter_density_smoothed,black_hole_id,gravity_well,neighbors"

    csv_writer
        .write_record(&[
            "timestep",
            "col",
            "row",
            "layer",
            "curvature",
            "matter_density",
            "is_black_hole",
            "rip_strength",
            "matter_density_smoothed",
            "black_hole_id",
            "gravity_well",
        ])
        .expect("Failed to write header");

    let mut grid = vec![vec![vec![Cell::new(); GRID_DEPTH]; GRID_HEIGHT]; GRID_WIDTH];
    seed_initial_curvature(&mut grid);
    stretch_curvature(&mut grid, "col");

    let mut time = 0.0;
    let time_step = 0.01;
    let initial_rip_strength = 10.0;
    let decay_rate = 0.05;
    let mut next_black_hole_id = 1;

    for timestep in 0..NUM_TIMESTEPS {
        let rip_strength = initial_rip_strength * f64::exp(-decay_rate * time);
        let mut raw_density: Vec<Vec<Vec<f64>>> =
            vec![vec![vec![0.0; GRID_DEPTH]; GRID_HEIGHT]; GRID_WIDTH];
        if timestep % 10 == 0 {
            println!("Progress: {:>3}%", (timestep * 100) / NUM_TIMESTEPS);
        }

        for x in 0..GRID_WIDTH {
            for y in 0..GRID_HEIGHT {
                for z in 0..GRID_DEPTH {
                    let cell = &mut grid[x][y][z];
                    cell.timestep = timestep;
                    cell.apply_gravity_interaction();
                    cell.rip_strength = rip_strength;
                    cell.gravity_well = (cell.curvature + cell.matter_density_smoothed) as f64;

                    if !cell.is_black_hole
                        && cell.curvature > CURVATURE_THRESHOLD
                        && cell.matter_density > COLLAPSE_DENSITY_THRESHOLD
                    {
                        cell.is_black_hole = true;
                        cell.black_hole_id = Some(next_black_hole_id);
                        next_black_hole_id += 1;
                        cell.matter_density = 0.0;
                    }

                    raw_density[x][y][z] = cell.matter_density;
                }
            }
        }

        let smoothed = smooth_density(&raw_density);
        for x in 0..GRID_WIDTH {
            for y in 0..GRID_HEIGHT {
                for z in 0..GRID_DEPTH {
                    let cell = &mut grid[x][y][z];
                    cell.matter_density_smoothed = smoothed[x][y][z] as f64;
                    csv_writer
                        .write_record(&[
                            cell.timestep.to_string(),
                            cell.col.to_string(),
                            cell.row.to_string(),
                            cell.layer.to_string(),
                            format!("{:.3}", cell.curvature),
                            format!("{:.6}", cell.matter_density),
                            u8::from(cell.is_black_hole).to_string(),
                            format!("{:.3}", cell.rip_strength),
                            format!("{:.6}", cell.matter_density_smoothed),
                            cell.black_hole_id.unwrap_or(0).to_string(),
                            format!("{:.6}", cell.gravity_well),
                        ])
                        .expect("Failed to write cell");
                    /*
                        writeln!(
                            writer,
                            "{},{},{},{},{:.3},{:.6},{},{:.3},{:.6},{},{:.6}",
                            cell.timestep,
                            cell.col,
                            cell.row,
                            cell.layer,
                            cell.curvature,
                            cell.matter_density,
                            u8::from(cell.is_black_hole),
                            cell.rip_strength,
                            cell.matter_density_smoothed,
                            cell.black_hole_id.unwrap_or(0),
                            cell.gravity_well // cell.neighbors
                                              // .iter()
                                              // .map(|(a, b, c)| format!("{},{},{}", a, b, c))
                                              // .collect::<Vec<_>>()
                                              // .join(";")
                        )
                        .unwrap();
                    */
                }
            }
        }
        time += time_step;
    }

    // writer.flush().unwrap();

    let count = grid
        .iter()
        .flat_map(|col| col.iter())
        .flat_map(|row| row.iter())
        .filter(|cell| cell.is_black_hole)
        .count();

    println!("Black holes created: {}", count);
    println!("Finished inflation simulation: data/inflation.csv.gz");
}

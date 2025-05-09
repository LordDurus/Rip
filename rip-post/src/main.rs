use csv::ReaderBuilder;
use csv::Writer;
use indicatif::ProgressBar;
use rip_core::cell::Cell;
use rip_core::helpers::create_gzip_writer;
use std::env;
use std::fs::File;
use std::io::BufReader;
use std::path::Path;

fn read_cells_from_csv<P: AsRef<Path>>(path: P) -> Vec<Vec<Cell>> {
    println!("Reading input from: {}", path.as_ref().display());
    let file = File::open(path).expect("Failed to open input file");
    let mut reader = ReaderBuilder::new()
        .has_headers(true)
        .from_reader(BufReader::new(file));

    let mut frames: Vec<Vec<Cell>> = Vec::new();
    for result in reader.deserialize() {
        let cell: Cell = result.expect("CSV parse error");
        let t = cell.timestep as usize;
        if frames.len() <= t {
            frames.resize_with(t + 1, Vec::new);
        }
        frames[t].push(cell);
    }
    frames
}

fn evolve_structure(frames: &mut [Vec<Cell>]) {
    let total = frames.iter().map(|f| f.len()).sum::<usize>();
    let pb = ProgressBar::new(total as u64);

    for frame in frames.iter_mut() {
        for cell in frame.iter_mut() {
            let gravity = cell.gravity_well;
            let density = cell.matter_density_smoothed;

            // Strengthen filaments if high gravity + density
            if gravity > 0.05 && density > 0.002 {
                cell.curvature += 0.01 * gravity;
            }

            // Dampen voids
            if gravity < 0.01 && density < 0.0005 {
                cell.curvature *= 0.95;
            }

            pb.inc(1);
        }
    }

    pb.finish_with_message("Processing complete");
}

fn write_output(path: &str, frames: &[Vec<Cell>]) {
    let writer = create_gzip_writer(path);
    let mut csv_writer = Writer::from_writer(writer);

    let total: usize = frames.iter().map(|f| f.len()).sum();
    let pb = ProgressBar::new(total as u64);

    for frame in frames {
        for cell in frame {
            csv_writer.serialize(cell).expect("Failed to write cell");
            pb.inc(1);
        }
    }

    pb.finish_with_message("Output written to structure.csv.gz");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: rip-post <input_file>");
        return;
    }

    let path = &args[1];
    let mut frames = read_cells_from_csv(path);
    let total_cells: usize = frames.iter().map(|f| f.len()).sum();
    println!(
        "Loaded {} frames with a total of {} cells",
        frames.len(),
        total_cells
    );
    println!("Starting Evolve Phase");
    evolve_structure(&mut frames);
    println!("Starting File write Phase");
    write_output("data/post.csv.gz", &frames);
}

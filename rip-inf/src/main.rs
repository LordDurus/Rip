mod inflation;
mod structure;
use std::env;

enum OutputMode {
    Structure,
    Inflation,
    All,
}

fn parse_mode() -> Option<OutputMode> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        return None;
    }
    match args[1].as_str() {
        "structure" => Some(OutputMode::Structure),
        "inflation" => Some(OutputMode::Inflation),
        "all" => Some(OutputMode::All),
        _ => None,
    }
}

fn main() {
    match parse_mode() {
        Some(OutputMode::Structure) => structure::run(),
        Some(OutputMode::Inflation) => inflation::run(),
        Some(OutputMode::All) => {
            structure::run();
            inflation::run();
        }
        None => {
            println!("Usage: cargo run -- <mode>");
            println!("Modes:");
            println!("  structure   Run the structure simulation");
            println!("  inflation   Run the inflation curve output");
            println!("  all         Run both simulations");
        }
    }
}

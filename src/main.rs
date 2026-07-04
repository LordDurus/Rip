use crate::database::app_settings::AppSetting;
use crate::database::database_setup::setup_database;
use crate::database::sqlite_provider::SqliteProvider;
use crate::helpers::show_settings::show_settings;
use colored::Colorize;

mod create_data;
mod database;
mod enums;
mod galaxy;
mod gravity;
mod helpers;
mod initial_geometry;

fn main() {
    // Sweep / append mode: when the RIP_APPEND env var is set, keep the existing
    // rip_data.db and add a NEW run (new run_id) instead of wiping it and
    // recopying the template. Unset (the default, e.g. run.bat) is unchanged:
    // force_reset = true, a fresh DB and run_id = 1 every time.
    let force_reset = std::env::var("RIP_APPEND").is_err();
    let conn = setup_database(force_reset).unwrap();
    let app_settings = AppSetting::get_settings(&conn);
    let mut db = SqliteProvider { conn };
    show_settings(&app_settings);

    // If NUM_CORES is -1, use all available threads. Otherwise, set the limit.
    if app_settings.num_cores != 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(app_settings.num_cores as usize)
            .build_global()
            .unwrap_or_else(|_| eprintln!("num_cores: Thread pool already initialized, skipping."));
    } else {
        // keep 1 CPU free to avoid freezing the system
        let threads = rayon::current_num_threads().saturating_sub(1).max(1);
        rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build_global()
            .unwrap_or_else(|_| eprintln!("Thread pool already initialized, skipping."));
    }

    println!("{}{} {}", "Thread pool: using ".cyan(), rayon::current_num_threads().to_string().yellow(), "threads".cyan());

    let start = std::time::Instant::now();
    if let Err(e) = create_data::run(&app_settings, &mut db) {
        eprintln!("Simulation error: {}", e);
    }
    let duration = start.elapsed();
    println!("{} {:?}", "All runs completed in".cyan(), duration);

    print!("\x07"); // Beep to signal completion
}

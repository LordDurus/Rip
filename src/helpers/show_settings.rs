use crate::AppSettings;
use colored::Colorize;

pub fn show_settings(settings: &AppSettings) {
    if !settings.quiet {
        "=== Simulation Configuration ===".blue();
        println!("{}{} {}", "RIP_INITIAL".cyan(), ":".yellow(), settings.rip_initial.to_string().cyan());
        println!("{}{} {}", "RIP_DECAY_RATE".cyan(), ":".yellow(), settings.rip_decay_rate.to_string().cyan());
        println!("{}{} {}", "RIP_MINIMUM_STRENGTH".cyan(), ":".yellow(), settings.rip_minimum_strength.to_string().cyan());
        println!("{}{} {}", "RIP_CURVATURE_WEIGHT".cyan(), ":".yellow(), settings.rip_curvature_weight.to_string().cyan());
        println!("{}{} {}", "RIP_DENSITY_WEIGHT".cyan(), ":".yellow(), settings.rip_density_weight.to_string().cyan());
        println!("{}{} {}", "DECAY_FACTOR".cyan(), ":".yellow(), settings.decay_factor.to_string().cyan());
        println!("{}{} {}", "TIME_STEP_SIZE".cyan(), ":".yellow(), settings.time_step_size.to_string().cyan());
        println!("{}{} {}", "MAX_SIMULATION_TIME".cyan(), ":".yellow(), settings.max_simulation_time.to_string().cyan());
        println!("{}{} {}", "NUM_TIMESTEPS".cyan(), ":".yellow(), settings.num_timesteps.to_string().cyan());
        println!("{}{} {}", "INF_GRID_WIDTH".cyan(), ":".yellow(), settings.inf_grid_width.to_string().cyan());
        println!("{}{} {}", "INF_GRID_HEIGHT".cyan(), ":".yellow(), settings.inf_grid_height.to_string().cyan());
        println!("{}{} {}", "INF_GRID_DEPTH".cyan(), ":".yellow(), settings.inf_grid_depth.to_string().cyan());
        println!("{}{} {}", "STRUCTURE_NUM_PARTICLES".cyan(), ":".yellow(), settings.structure_num_particles.to_string().cyan());
        println!("{}{} {}", "CURVATURE_THRESHOLD".cyan(), ":".yellow(), settings.curvature_threshold.to_string().cyan());
        println!("{}{} {}", "COLLAPSE_DENSITY_THRESHOLD".cyan(), ":".yellow(), settings.collapse_density_threshold.to_string().cyan());
        println!("{}{} {}", "DARK_MATTER_RATIO".cyan(), ":".yellow(), settings.dark_matter_ratio.to_string().cyan());
        println!("{}{} {}", "DARK_GRAVITY_BOOST".cyan(), ":".yellow(), settings.dark_gravity_boost.to_string().cyan());
        println!("{}{} {}", "GRAVITY".cyan(), ":".yellow(), settings.gravity.to_string().cyan());
        println!("{}{} {}", "LIGHT_SPEED".cyan(), ":".yellow(), settings.light_speed.to_string().cyan());
        println!("{}{} {}", "RIP_DECAY_MECHANISM".cyan(), ":".yellow(), settings.rip_decay_mechanism.to_string().cyan());
        "===============================".blue();
    }
}

use crate::AppSettings;

pub fn show_settings(settings: &AppSettings) {
    if !settings.quiet {
        println!("=== Simulation Configuration ===");
        println!("RIP_INITIAL:              {}", settings.rip_initial);
        println!("RIP_DECAY_RATE:           {}", settings.rip_decay_rate);
        println!("RIP_MINIMUM_STRENGTH:     {}", settings.rip_minimum_strength);
        println!("RIP_CURVATURE_WEIGHT:     {}", settings.rip_curvature_weight);
        println!("RIP_DENSITY_WEIGHT:       {}", settings.rip_density_weight);
        println!("DECAY_FACTOR:             {}", settings.decay_factor);
        println!("TIME_STEP_SIZE:           {}", settings.time_step_size);
        println!("MAX_SIMULATION_TIME:      {}", settings.max_simulation_time);
        println!("NUM_TIMESTEPS:            {}", settings.num_timesteps);
        println!("INF_GRID_WIDTH:           {}", settings.inf_grid_width);
        println!("INF_GRID_HEIGHT:          {}", settings.inf_grid_height);
        println!("INF_GRID_DEPTH:           {}", settings.inf_grid_depth);
        println!("STRUCTURE_NUM_PARTICLES:  {}", settings.structure_num_particles);
        println!("CURVATURE_THRESHOLD:      {}", settings.curvature_threshold);
        println!("COLLAPSE_DENSITY_THRESHOLD: {}", settings.collapse_density_threshold);
        println!("DARK_MATTER_RATIO:        {}", settings.dark_matter_ratio);
        println!("DARK_GRAVITY_BOOST:       {}", settings.dark_gravity_boost);
        println!("GRAVITY:                  {}", settings.gravity);
        println!("LIGHT_SPEED:              {}", settings.light_speed);
        println!("RIP_DECAY_MECHANISM:      {}", settings.rip_decay_mechanism);
        println!("===============================");
    }
}

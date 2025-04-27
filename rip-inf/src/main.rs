use rip_core::config::SimulationConfig;
use rip_core::helpers::exponential_decay;
use std::fs::{File, create_dir_all};
use std::io::{BufWriter, Write};

fn main() -> std::io::Result<()> {
    // Load the simulation configuration
    let config = SimulationConfig::default();

    let mut time = 0.0;
    let mut scale_factor = 1.0;

    // make sure the data folder exists
    create_dir_all("data")?;

    // create the CSV file in the data folder
    let file = File::create("data/simulation.csv")?;
    let mut writer = BufWriter::new(file);

    // write CSV header
    writeln!(writer, "time,rip_strength,scale_factor")?;

    while time <= config.max_simulation_time {
        // use the helper to calculate rip field decay
        let rip_strength = exponential_decay(config.rip_initial, config.rip_decay_rate, time);

        // calculate expansion rate (Hubble parameter)
        let expansion_rate = rip_strength.sqrt();

        // update scale factor
        scale_factor *= (expansion_rate * config.time_step_size).exp();

        // write current step to CSV
        writeln!(
            writer,
            "{:.6},{:.6},{:.6}",
            time, rip_strength, scale_factor
        )?;

        // advance time
        time += config.time_step_size;
    }

    println!("Simulation complete. Results written to data/simulation.csv.");
    return Ok(());
}

use rand::prelude::*;
use rip_core::helpers::create_gzip_writer;
use std::f64::consts::PI;
use std::io::Write;

const NUM_PARTICLES: usize = 1000;

fn initialize_particles(
    rng: &mut ThreadRng,
    positions: &mut Vec<(f64, f64, f64)>,
    velocities: &mut Vec<(f64, f64, f64)>,
) {
    for i in 0..NUM_PARTICLES {
        let theta = rng.gen_range(0.0..2.0 * PI);
        let phi = rng.gen_range(0.0..PI);
        let r = rng.gen_range(0.8..1.2);

        let x = r * phi.sin() * theta.cos();
        let y = r * phi.sin() * theta.sin();
        let z = r * phi.cos();

        let vx = rng.gen_range(-0.05..0.05);
        let vy = rng.gen_range(-0.05..0.05);
        let vz = rng.gen_range(-0.05..0.05);

        positions[i] = (x, y, z);
        velocities[i] = (vx, vy, vz);
    }
}

pub fn run() {
    let mut writer = create_gzip_writer("data/structure.csv.gz");

    // write header
    writeln!(writer, "time,rip_strength,scale_factor,x,y,z,vx,vy,vz")
        .expect("failed to write header");

    let mut rng = rand::thread_rng();
    let mut positions = vec![(0.0, 0.0, 0.0); NUM_PARTICLES];
    let mut velocities = vec![(0.0, 0.0, 0.0); NUM_PARTICLES];

    // initialize particle positions in an asymmetrical sphere
    initialize_particles(&mut rng, &mut positions, &mut velocities);

    let mut time = 0.0;
    let dt = 0.01;
    let mut scale_factor = 2.718281828459045;
    let mut rip_strength = 10000.0;
    let mut last_reported_second = -1;

    while time <= 10.0 {
        let current_second = (time as f32).floor() as i32;
        if current_second != last_reported_second {
            println!("progress: {:.0}/10 seconds simulated", time);
            last_reported_second = current_second;
        }

        let mut buffer = String::new();

        for i in 0..NUM_PARTICLES {
            let (x, y, z) = positions[i];
            let (vx, vy, vz) = velocities[i];
            use std::fmt::Write as _;
            write!(
                &mut buffer,
                "{:.6},{:.6},{:.6},{:.6},{:.6},{:.6},{:.6},{:.6},{:.6}\n",
                time, rip_strength, scale_factor, x, y, z, vx, vy, vz
            )
            .unwrap();
        }

        writer
            .write_all(buffer.as_bytes())
            .expect("failed to write batch");

        // update scale factor and rip_strength
        scale_factor *= 1.05;
        rip_strength *= 0.95;

        // update positions
        for (i, pos) in positions.iter_mut().enumerate() {
            let (vx, vy, vz) = velocities[i];
            pos.0 += vx * dt;
            pos.1 += vy * dt;
            pos.2 += vz * dt;
        }

        time += dt;
    }
}

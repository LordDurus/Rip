#[derive(Debug)]
struct Galaxy {
    mass: f64,
    bh_mass: f64,
    rip_events: Vec<(usize, f64)>,
}

impl Galaxy {
    fn new(app_settings: &AppSettings) -> Self {
        Self {
            mass: app_settings.initial_mass,
            bh_mass: app_settings.initial_bh_mass,
            rip_events: Vec::new(),
        }
    }

    fn simulate_step(
        &mut self,
        time: usize,
        app_settings: &AppSettings,
        rng: &mut ThreadRng,
    ) -> f64 {
        let matter_inflow = self.random_inflow(rng);
        self.bh_mass += matter_inflow;
        self.mass -= matter_inflow;

        if self.rip_chance(time, app_settings, rng) {
            let lost_mass = self.destroy_mass(matter_inflow);
            self.bh_mass -= lost_mass;
            self.rip_events.push((time, lost_mass));
            return lost_mass;
        }
        0.0
    }

    fn random_inflow(&self, rng: &mut ThreadRng) -> f64 {
        rng.gen_range(1e6..1e8)
    }

    fn rip_chance(&self, time: usize, app_settings: &AppSettings, rng: &mut ThreadRng) -> bool {
        let base_chance = 0.00009;
        let scale = (self.bh_mass / app_settings.initial_bh_mass)
            * (time as f64 / app_settings.sim_duration as f64).ln_1p();
        rng.gen_bool((base_chance * scale).min(1.0))
    }

    fn destroy_mass(&self, mass: f64) -> f64 {
        let mut rng = rand::thread_rng();
        mass * rng.gen_range(0.1..=0.5)
    }
}

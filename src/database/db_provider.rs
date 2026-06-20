use crate::database::entities::cell::Cell;
use crate::database::entities::cell_position::CellPosition;
use crate::database::entities::run::Run;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use crate::galaxy::Galaxy;
use rusqlite::Result;

#[allow(dead_code)]
pub trait DbProvider {
    /// Start a new run. Snapshots app_setting into run_setting and returns the Run.
    fn start_run(&mut self, seed: u64, notes: Option<&str>) -> Result<Run>;

    /// Mark a run as completed (sets ended_at and status).
    fn complete_run(&mut self, run_id: i64) -> Result<()>;

    /// Mark a run as failed.
    fn fail_run(&mut self, run_id: i64, reason: String) -> Result<()>;

    fn insert_particle_batch(&mut self, particles: &[StructureParticle]) -> Result<()>;
    fn save_all_cells(&mut self, run_id: i64, grid: &mut Vec<Vec<Vec<Cell>>>) -> Result<()>;
    fn record_timestep_summary(&mut self, timestep: usize, step_duration_myr: f64, grid: &Vec<Vec<Vec<Cell>>>, run_id: i64, scale_factor: f64, total_matter: f64, galaxy_count: i64) -> Result<()>;
    fn get_or_insert_cell_position(&mut self, column: usize, row: usize) -> CellPosition;
    fn log_message(&mut self, run_id: i64, module: &str, level: LogLevel, message: &str) -> rusqlite::Result<()>;
    fn load_custom_density(&self) -> rusqlite::Result<Vec<(usize, usize, usize, f64)>>;

    /// Insert a galaxy row and stamp the real DB-assigned galaxy_id back onto the struct.
    /// Called once per galaxy: at run start for seeds, at discovery timestep for late-formers.
    fn insert_galaxy(&mut self, galaxy: &mut Galaxy) -> Result<()>;

    /// Snapshot galaxy state for this timestep. Called every timestep for each active galaxy.
    fn record_galaxy_timestep(&mut self, galaxy: &Galaxy, timestep: usize, smbh_count: i64) -> Result<()>;

    /// Mark a galaxy inactive (absorbed by merger). Called when process_mergers deactivates one.
    fn deactivate_galaxy(&mut self, galaxy_id: i64) -> Result<()>;

    /// Batch-insert newly-born galaxies in a single transaction, stamping the real
    /// DB-assigned galaxy_id back onto each struct (in input order). Use instead of
    /// looping insert_galaxy — one commit, not one per row.
    fn insert_galaxies(&mut self, galaxies: &mut [&mut Galaxy]) -> Result<()>;

    /// Batch-snapshot galaxy state for this timestep in a single transaction.
    /// `counts` holds the per-galaxy SMBH count, aligned by index with `galaxies`.
    fn record_galaxy_timesteps(&mut self, galaxies: &[Galaxy], counts: &[i64], timestep: usize) -> Result<()>;

    /// Batch-deactivate galaxies (merged/dissolved) in a single transaction.
    fn deactivate_galaxies(&mut self, galaxy_ids: &[i64]) -> Result<()>;
}

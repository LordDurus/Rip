use crate::database::entities::cell::Cell;
use crate::database::entities::cell_position::CellPosition;
use crate::database::entities::run::Run;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use rusqlite::Result;

pub trait DbProvider {
    /// Start a new run. Snapshots app_setting into run_setting and returns the Run.
    fn start_run(&mut self, seed: u64, notes: Option<&str>) -> Result<Run>;

    /// Mark a run as completed (sets ended_at and status).
    fn complete_run(&mut self, run_id: i64) -> Result<()>;

    /// Mark a run as failed.
    fn fail_run(&mut self, run_id: i64, reason: String) -> Result<()>;

    fn insert_particle_batch(&mut self, particles: &[StructureParticle]) -> Result<()>;
    fn save_all_cells(&mut self, run_id: i64, grid: &mut Vec<Vec<Vec<Cell>>>) -> Result<()>;
    fn record_timestep_summary(&mut self, timestep: usize, step_duration_myr: f64, grid: &Vec<Vec<Vec<Cell>>>, run_id: i64) -> Result<()>;
    fn get_or_insert_cell_position(&mut self, column: usize, row: usize) -> CellPosition;
    fn log_message(&mut self, run_id: i64, module: &str, level: LogLevel, message: &str) -> rusqlite::Result<()>;

    fn load_custom_density(&self) -> rusqlite::Result<Vec<(usize, usize, usize, f64)>>;
}

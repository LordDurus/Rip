use crate::database::entities::cell::Cell;
use crate::database::entities::cell_position::CellPosition;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::LogLevel;
use rusqlite::Result;

pub trait DbProvider {
    fn insert_particle_batch(&mut self, particles: &[StructureParticle]) -> Result<()>;
    fn save_all_cells(&mut self, grid: &mut Vec<Vec<Vec<Cell>>>) -> Result<()>;
    fn record_rip_field_summary(
        &mut self,
        timestep: usize,
        step_duration_myr: f64,
        grid: &Vec<Vec<Vec<Cell>>>,
    ) -> Result<()>;
    fn get_or_insert_cell_position(&mut self, col: usize, row: usize) -> CellPosition;
    fn log_message(&mut self, module: &str, level: LogLevel, message: &str)
    -> rusqlite::Result<()>;
}

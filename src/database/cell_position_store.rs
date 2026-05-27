use crate::database::entities::cell_position::CellPosition;

pub trait CellPositionStore {
    fn get_or_insert_cell_position(&self, col: usize, row: usize) -> CellPosition;
}

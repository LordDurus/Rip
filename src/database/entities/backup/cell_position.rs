#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct CellPosition {
    pub cell_position_id: i64,
    pub col: usize,
    pub row: usize,
}

use crate::database::entities::cell::Cell;
use std::sync::Arc;
use std::sync::Mutex;

pub fn set_as_black_hole(cell: &mut Cell, next_black_hole_id: &Arc<Mutex<u64>>) {
    cell.is_black_hole = true;
    cell.is_star = false;
    let mut id = next_black_hole_id.lock().unwrap();
    cell.black_hole_id = Some(*id);
    *id += 1;
    drop(id);

    // cell.matter_density = 1.0e30;
    // cell.dimple_strength = 1.0e30;
}

/// Relax a black hole back into an ordinary cell once it has drained below the
/// reversal threshold. Mirror of `set_as_black_hole`.
pub fn revert_black_hole(cell: &mut Cell) {
    cell.is_black_hole = false;
    cell.black_hole_id = None;
    cell.is_rip_induced = false;
    cell.is_supermassive = false;
    cell.smbh_rip_contribution = false;
    cell.is_star = false;
    // Intentionally left alone: matter_density / dimple_strength / curvature.
    // matter_density now holds the real residual, which re-enters total_matter on
    // this flip — that's your contraction kick. mass recomputes from it next step.
}

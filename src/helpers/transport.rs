use crate::database::app_settings::AppSettings;
use crate::database::entities::cell::Cell;
use rayon::prelude::*;

/// Gravity-driven matter transport (two-pass, conservative).
///
/// Pass 1 computes each non-black-hole cell's outflow to its six face-neighbours
/// from a read-only view of the grid; pass 2 applies them as a gather, so it is
/// race-free and conserves total matter exactly. Matter aimed at a black-hole
/// neighbour stays with the source (black holes don't participate).
///
/// This is the conservative replacement for the old in-place `accretion` term:
/// matter moves *between* cells along the gravity direction rather than being
/// grown out of nothing.
pub fn apply_matter_transport(grid: &mut Vec<Vec<Vec<Cell>>>, settings: &AppSettings, step_duration: f64) {
    let _ = step_duration; // direction-normalized form doesn't need dt; kept for signature symmetry
    let (h_dim, w_dim, d_dim) = (settings.inf_grid_height, settings.inf_grid_width, settings.inf_grid_depth);
    const CFL: f64 = 0.25; // hard ceiling: never move more than this fraction of a cell per step

    // read-only BH mask — pass 2 mutates the grid, so it can't read neighbours off it
    let is_bh: Vec<Vec<Vec<bool>>> = grid.iter().map(|p| p.iter().map(|r| r.iter().map(|c| c.is_black_hole).collect()).collect()).collect();

    // outflow[h][w][d] = [-h, +h, -w, +w, -d, +d]
    let mut outflow = vec![vec![vec![[0.0f64; 6]; d_dim]; w_dim]; h_dim];

    // Pass 1: read the grid immutably (shared), write only `outflow`.
    {
        let cells = &*grid;
        outflow.par_iter_mut().enumerate().for_each(|(h, plane)| {
            plane.iter_mut().enumerate().for_each(|(w, rowf)| {
                rowf.iter_mut().enumerate().for_each(|(d, of)| {
                    let c = &cells[h][w][d];
                    if c.is_black_hole || c.matter_density <= 0.0 {
                        return;
                    }
                    let density = c.matter_density;

                    let (gh, gw, gd) = (c.gravity_x, c.gravity_y, c.gravity_z);
                    let l1 = gh.abs() + gw.abs() + gd.abs();
                    if l1 <= 0.0 {
                        return;
                    }

                    let move_total = (settings.transport_rate * density).min(CFL * density);

                    let mut raw = [0.0f64; 6];
                    raw[if gh > 0.0 { 1 } else { 0 }] = move_total * gh.abs() / l1;
                    raw[if gw > 0.0 { 3 } else { 2 }] = move_total * gw.abs() / l1;
                    raw[if gd > 0.0 { 5 } else { 4 }] = move_total * gd.abs() / l1;
                    *of = raw;
                });
            });
        });
    }

    // Pass 2: gather. new = old − (outflow to non-BH neighbours) + (neighbours' outflow toward me)
    grid.par_iter_mut().enumerate().for_each(|(h, plane)| {
        plane.iter_mut().enumerate().for_each(|(w, rowc)| {
            rowc.iter_mut().enumerate().for_each(|(d, cell)| {
                if cell.is_black_hole {
                    return;
                }
                let (hm, hp) = ((h + h_dim - 1) % h_dim, (h + 1) % h_dim);
                let (wm, wp) = ((w + w_dim - 1) % w_dim, (w + 1) % w_dim);
                let (dm, dp) = ((d + d_dim - 1) % d_dim, (d + 1) % d_dim);

                let mine = outflow[h][w][d];
                let mut sent = 0.0;
                if !is_bh[hm][w][d] {
                    sent += mine[0];
                }
                if !is_bh[hp][w][d] {
                    sent += mine[1];
                }
                if !is_bh[h][wm][d] {
                    sent += mine[2];
                }
                if !is_bh[h][wp][d] {
                    sent += mine[3];
                }
                if !is_bh[h][w][dm] {
                    sent += mine[4];
                }
                if !is_bh[h][w][dp] {
                    sent += mine[5];
                }

                let recv = outflow[hp][w][d][0] + outflow[hm][w][d][1] + outflow[h][wp][d][2] + outflow[h][wm][d][3] + outflow[h][w][dp][4] + outflow[h][w][dm][5];

                cell.matter_density = (cell.matter_density - sent + recv).max(0.0);
            });
        });
    });
}

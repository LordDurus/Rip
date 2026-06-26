use crate::database::app_settings::AppSetting;
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
pub fn apply_matter_transport(grid: &mut Vec<Vec<Vec<Cell>>>, settings: &AppSetting, step_duration: f64) {
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

/// Gravity-driven dark-matter dimple transport (Tier 1, collisionless).
///
/// Same conservative two-pass structure as `apply_matter_transport`, but it
/// advects `rip_dimple` instead of `matter_density` and is *collisionless*:
/// every cell participates and flux crosses black-hole cells freely (the dimple
/// is geometry, not baryonic matter — it passes through). The dimple falls down
/// the total gravity gradient (which already includes its own self-gravity via
/// the Poisson source), so it clusters into wells and drains voids, producing
/// the density contrast that lensing needs. Conserves total rip_dimple exactly;
/// expansion dilution remains the only sink, so the validated boundedness is
/// unchanged.
///
/// NOTE: this is overdamped (no momentum) — it settles into wells rather than
/// streaming through them, so it yields halos but NOT the Bullet-Cluster
/// pass-through offset. That offset needs multi-streaming, i.e. the Tier 2
/// particle/momentum dynamics. Setting dimple_transport_rate = 0 disables this
/// pass and recovers the pure static fossil field.
pub fn apply_dimple_transport(grid: &mut Vec<Vec<Vec<Cell>>>, settings: &AppSetting, step_duration: f64) {
    let _ = step_duration; // direction-normalized form doesn't need dt
    if settings.dimple_transport_rate <= 0.0 {
        return; // movement disabled — pure static fossil (pre-Tier-1 behaviour)
    }
    let (h_dim, w_dim, d_dim) = (settings.inf_grid_height, settings.inf_grid_width, settings.inf_grid_depth);
    const CFL: f64 = 0.25; // never move more than this fraction of a cell's dimple per step

    // outflow[h][w][d] = [-h, +h, -w, +w, -d, +d]
    let mut outflow = vec![vec![vec![[0.0f64; 6]; d_dim]; w_dim]; h_dim];

    // Pass 1: read the grid immutably, write only `outflow`.
    {
        let cells = &*grid;
        outflow.par_iter_mut().enumerate().for_each(|(h, plane)| {
            plane.iter_mut().enumerate().for_each(|(w, rowf)| {
                rowf.iter_mut().enumerate().for_each(|(d, of)| {
                    let c = &cells[h][w][d];
                    if c.rip_dimple <= 0.0 {
                        return;
                    }
                    let amount = c.rip_dimple;

                    let (gh, gw, gd) = (c.gravity_x, c.gravity_y, c.gravity_z);
                    let l1 = gh.abs() + gw.abs() + gd.abs();
                    if l1 <= 0.0 {
                        return;
                    }

                    let move_total = (settings.dimple_transport_rate * amount).min(CFL * amount);

                    let mut raw = [0.0f64; 6];
                    raw[if gh > 0.0 { 1 } else { 0 }] = move_total * gh.abs() / l1;
                    raw[if gw > 0.0 { 3 } else { 2 }] = move_total * gw.abs() / l1;
                    raw[if gd > 0.0 { 5 } else { 4 }] = move_total * gd.abs() / l1;
                    *of = raw;
                });
            });
        });
    }

    // Pass 2: gather. Collisionless — no black-hole masking, so every unit a cell
    // sends is received by exactly one neighbour (total rip_dimple conserved).
    grid.par_iter_mut().enumerate().for_each(|(h, plane)| {
        plane.iter_mut().enumerate().for_each(|(w, rowc)| {
            rowc.iter_mut().enumerate().for_each(|(d, cell)| {
                let (hm, hp) = ((h + h_dim - 1) % h_dim, (h + 1) % h_dim);
                let (wm, wp) = ((w + w_dim - 1) % w_dim, (w + 1) % w_dim);
                let (dm, dp) = ((d + d_dim - 1) % d_dim, (d + 1) % d_dim);

                let sent: f64 = outflow[h][w][d].iter().sum();

                let recv = outflow[hp][w][d][0] + outflow[hm][w][d][1] + outflow[h][wp][d][2] + outflow[h][wm][d][3] + outflow[h][w][dp][4] + outflow[h][w][dm][5];

                cell.rip_dimple = (cell.rip_dimple - sent + recv).max(0.0);
            });
        });
    });
}

/// Gas momentum transport (Bullet Cluster, collisional).
///
/// The baryonic counterpart to the collisionless dimple particles: gives the gas
/// (matter_density) inertia and a ram-pressure shock so it can lag at a collision,
/// while the dark-matter dimple sails through. Replaces apply_matter_transport when
/// gas_momentum_enabled; the validated overdamped path is untouched when it is off.
///
/// Three stages, same conservative two-pass spirit as apply_matter_transport:
///   1. Velocity prepass: v += g*dt per non-BH cell, so gravity-driven infall
///      ACCUMULATES (inertia — the velocity persists across steps via the in-memory
///      gas_velocity grid). Then ram-pressure drag damps the velocity wherever the
///      gas density exceeds gas_shock_density (the two-clump pileup interface), so
///      the gas decelerates and lags. drag_coefficient = 0 -> no drag -> the gas is
///      effectively collisionless and passes through like the dimple (no offset);
///      that is the A/B null that proves drag is the mechanism.
///   2. Outflow pass: each non-BH cell sends matter to its face-neighbours along the
///      velocity direction, fraction = (|v|*dt) capped at CFL, distributed by the L1
///      velocity components — exactly the apply_matter_transport scheme with velocity
///      substituted for the gravity direction. Read-only over grid + velocity.
///   3. Gather pass: conservative gather; matter aimed at a black-hole neighbour
///      stays with the source (gas does not enter black holes), so total matter is
///      conserved among non-BH cells.
///
/// NOTE: the velocity field is Eulerian (per-cell, gravity-integrated with inertia),
/// not full Lagrangian momentum advection — the gas gains inertia and a shock lag,
/// which is what the Bullet Cluster offset needs, but velocity is not itself carried
/// with the advected parcel. If that approximation proves too lossy, momentum
/// advection is the phase-2 refinement.
pub fn apply_gas_momentum(grid: &mut Vec<Vec<Vec<Cell>>>, gas_velocity: &mut Vec<Vec<Vec<[f64; 3]>>>, settings: &AppSetting, step_duration: f64) {
    let dt = step_duration;
    let (h_dim, w_dim, d_dim) = (settings.inf_grid_height, settings.inf_grid_width, settings.inf_grid_depth);
    const CFL: f64 = 0.25; // never move more than this fraction of a cell per step
    let drag = settings.gas_drag_coefficient;
    let shock = settings.gas_shock_density;
    let cs = settings.gas_sound_speed;
    let pressure_on = settings.gas_pressure_enabled && cs > 0.0;

    // read-only BH mask — pass 3 mutates the grid, so it can't read neighbours off it
    let is_bh: Vec<Vec<Vec<bool>>> = grid.iter().map(|p| p.iter().map(|r| r.iter().map(|c| c.is_black_hole).collect()).collect()).collect();

    // Pass 1: integrate velocity under gravity (inertia), add isothermal thermal
    // pressure (Jeans support) with a sound-Courant clamp, then ram-pressure drag.
    {
        let cells = &*grid;
        gas_velocity.par_iter_mut().enumerate().for_each(|(h, plane)| {
            plane.iter_mut().enumerate().for_each(|(w, rowv)| {
                rowv.iter_mut().enumerate().for_each(|(d, v)| {
                    let c = &cells[h][w][d];
                    if c.is_black_hole || c.matter_density <= 0.0 {
                        *v = [0.0; 3]; // no gas here -> no bulk velocity
                        return;
                    }
                    v[0] += c.gravity_x * dt;
                    v[1] += c.gravity_y * dt;
                    v[2] += c.gravity_z * dt;

                    // Isothermal thermal pressure: P = c_s^2 * rho, so the gas feels
                    // a = -c_s^2 * grad(rho) / rho, pushing it down its own density
                    // gradient -- the Jeans support that balances self-gravity. The
                    // gradient reads matter_density ONLY (the gas field, not the dimple),
                    // central differences with periodic wrap and dx = 1 cell. A black-hole
                    // neighbour is clamped to the local density, making the rip boundary a
                    // no-flux face (no spurious push into or out of a BH). Gated on
                    // pressure_on so the disabled path stays byte-identical to before.
                    if pressure_on {
                        const RHO_FLOOR: f64 = 1e-12;
                        let rho = c.matter_density.max(RHO_FLOOR);
                        let (hm, hp) = ((h + h_dim - 1) % h_dim, (h + 1) % h_dim);
                        let (wm, wp) = ((w + w_dim - 1) % w_dim, (w + 1) % w_dim);
                        let (dm, dp) = ((d + d_dim - 1) % d_dim, (d + 1) % d_dim);
                        // BH neighbour -> local density => zero gradient across that face.
                        let rho_at = |hh: usize, ww: usize, dd: usize| -> f64 {
                            let n = &cells[hh][ww][dd];
                            if n.is_black_hole { rho } else { n.matter_density }
                        };
                        let grad_h = 0.5 * (rho_at(hp, w, d) - rho_at(hm, w, d));
                        let grad_w = 0.5 * (rho_at(h, wp, d) - rho_at(h, wm, d));
                        let grad_d = 0.5 * (rho_at(h, w, dp) - rho_at(h, w, dm));
                        let k = -(cs * cs) / rho * dt; // v += a*dt = -(c_s^2/rho)*grad(rho)*dt
                        v[0] += k * grad_h;
                        v[1] += k * grad_w;
                        v[2] += k * grad_d;

                        // Sound Courant guard: keep (|v| + c_s)*dt within the CFL budget so
                        // the explicit pressure update can't grow v into a sawtooth from
                        // under-resolved sound waves. Uses the same L1 speed proxy as the
                        // advection flux below, so Pass 2's cap is never the binding limit
                        // here. If c_s alone exceeds the budget (c_s*dt >= CFL) vmax clamps
                        // to 0 and the gas freezes -- a visible signal to lower
                        // GAS_SOUND_SPEED or TIME_STEP_SIZE, not a silent blowup.
                        let l1 = v[0].abs() + v[1].abs() + v[2].abs();
                        let vmax = (CFL / dt - cs).max(0.0);
                        if l1 > vmax && l1 > 0.0 {
                            let s = vmax / l1;
                            v[0] *= s;
                            v[1] *= s;
                            v[2] *= s;
                        }
                    }

                    if drag > 0.0 && c.matter_density > shock {
                        let damp = (1.0 - drag * dt).max(0.0);
                        v[0] *= damp;
                        v[1] *= damp;
                        v[2] *= damp;
                    }
                });
            });
        });
    }

    // Pass 2: outflow of matter_density along the velocity field (CFL-capped).
    let mut outflow = vec![vec![vec![[0.0f64; 6]; d_dim]; w_dim]; h_dim];
    {
        let cells = &*grid;
        let vel = &*gas_velocity;
        outflow.par_iter_mut().enumerate().for_each(|(h, plane)| {
            plane.iter_mut().enumerate().for_each(|(w, rowf)| {
                rowf.iter_mut().enumerate().for_each(|(d, of)| {
                    let c = &cells[h][w][d];
                    if c.is_black_hole || c.matter_density <= 0.0 {
                        return;
                    }
                    let v = vel[h][w][d];
                    let l1 = v[0].abs() + v[1].abs() + v[2].abs();
                    if l1 <= 0.0 {
                        return;
                    }
                    let density = c.matter_density;
                    let move_total = ((l1 * dt).min(CFL)) * density; // fraction moved = |v|*dt capped at CFL
                    let mut raw = [0.0f64; 6];
                    raw[if v[0] > 0.0 { 1 } else { 0 }] = move_total * v[0].abs() / l1;
                    raw[if v[1] > 0.0 { 3 } else { 2 }] = move_total * v[1].abs() / l1;
                    raw[if v[2] > 0.0 { 5 } else { 4 }] = move_total * v[2].abs() / l1;
                    *of = raw;
                });
            });
        });
    }

    // Pass 3: gather. new = old − (outflow to non-BH neighbours) + (neighbours' inflow).
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

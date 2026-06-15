use crate::database::app_settings::AppSetting;
use crate::database::entities::cell::Cell;
use crate::enums::rip_decay_mechanism::RipDecayMechanism;

pub fn compute_rip_decay(mechanism: &RipDecayMechanism, cell: &Cell, current_rip: f64, _timestep: usize, step_duration: f64) -> f64 {
    match mechanism {
        RipDecayMechanism::None => 0.0,

        RipDecayMechanism::TimeOnly { rate } => current_rip * rate * step_duration,

        RipDecayMechanism::SelfHealing { base_rate, density_damping } => {
            let local_resistance = 1.0 + density_damping * (cell.curvature + cell.matter_density);
            current_rip * base_rate * local_resistance * step_duration
        }

        RipDecayMechanism::MatterCoupled { rate, matter_threshold } => {
            if cell.matter_density < *matter_threshold {
                current_rip * rate * step_duration
            } else {
                0.0
            }
        }

        RipDecayMechanism::InverseStrength { rate } => {
            let safe = current_rip.max(1e-6);
            (rate / safe) * step_duration
        }

        RipDecayMechanism::Diffusive { .. } => 0.0, // handled in a separate pass
    }
}

#[inline(always)]
pub fn compute_cell_rip_strength(timestep: usize, cell: &Cell, settings: &AppSetting, decay_mechanism: &RipDecayMechanism, step_duration: f64) -> f64 {
    if cell.is_black_hole {
        return 0.0; // or some sentinel; black holes don't follow this formula
    }

    let ramp = 1.0 - f64::exp(-settings.rip_decay_rate * timestep as f64);
    let healing = 1.0 / (1.0 + cell.curvature + cell.matter_density);
    let rip_strength = settings.rip_initial * ramp * healing;
    let modifier = 1.0 + settings.rip_curvature_weight * cell.curvature + settings.rip_density_weight * cell.matter_density;

    let natural_strength = rip_strength * modifier;

    // Apply mechanism-based decay
    let decay = compute_rip_decay(decay_mechanism, cell, natural_strength, timestep, step_duration);

    (natural_strength - decay).clamp(settings.rip_minimum_strength, 1.0e6)
}

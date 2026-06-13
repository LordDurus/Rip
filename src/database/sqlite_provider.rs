use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::database::entities::cell_position::CellPosition;
use crate::database::entities::run::Run;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::log_level::LogLevel;
use rusqlite::{Connection, Result, params};

pub struct SqliteProvider {
    pub conn: Connection,
}

impl DbProvider for SqliteProvider {
    fn load_custom_density(&self) -> Result<Vec<(usize, usize, usize, f64)>> {
        Err(rusqlite::Error::FromSqlConversionFailure(
            0,
            rusqlite::types::Type::Null,
            Box::new(std::io::Error::new(std::io::ErrorKind::Unsupported, "load_custom_density is not yet implemented")),
        ))
    }

    fn start_run(&mut self, seed: u64, notes: Option<&str>) -> Result<Run> {
        let started_at = get_current_date_time().to_string();
        // If you don't already use chrono, alternative below.

        let tx = self.conn.transaction()?;

        tx.execute(
            "insert into run (started_at, status, seed, notes) values (?1, 'running', ?2, ?3)",
            params![started_at, seed as i64, notes],
        )?;
        let run_id = tx.last_insert_rowid();

        // Snapshot current app_setting into run_setting
        tx.execute(
            "insert into run_setting (run_id, key, value, datatype)
						 select ?1, ltrim(rtrim(key)), ltrim(rtrim(value)), ltrim(rtrim(datatype))
						 from app_setting",
            params![run_id],
        )?;

        tx.commit()?;

        Ok(Run {
            run_id,
            started_at,
            ended_at: None,
            status: "running".to_string(),
            seed,
            notes: notes.map(|s| s.to_string()),
        })
    }

    fn complete_run(&mut self, run_id: i64) -> Result<()> {
        let ended_at = get_current_date_time().to_string();
        self.conn.execute("update run set ended_at = ?1, status = 'completed' where run_id = ?2", params![ended_at, run_id])?;
        Ok(())
    }

    fn fail_run(&mut self, run_id: i64, reason: String) -> Result<()> {
        let ended_at = get_current_date_time().to_string();
        self.conn.execute(
            "update run set ended_at = ?1, status = 'failed', notes = coalesce(notes || ' | ', '') || ?2
						 where run_id = ?3",
            params![ended_at, reason, run_id],
        )?;
        Ok(())
    }

    fn insert_particle_batch(&mut self, particles: &[StructureParticle]) -> Result<()> {
        let tx = self.conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "insert into structure_particle (
										time, rip_strength, scale_factor,
										position_x, position_y, position_z,
										velocity_x, velocity_y, velocity_z
								) values (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            )?;

            for particle in particles {
                stmt.execute(params![
                    particle.time,
                    particle.rip_strength,
                    particle.scale_factor,
                    particle.position_x,
                    particle.position_y,
                    particle.position_z,
                    particle.velocity_x,
                    particle.velocity_y,
                    particle.velocity_z,
                ])?;
            }
        }
        tx.commit()
    }

    fn save_all_cells(&mut self, run_id: i64, grid: &mut Vec<Vec<Vec<Cell>>>) -> Result<()> {
        let tx = self.conn.transaction()?;
        let mut buffer = Vec::with_capacity(1000);

        for col in grid.iter() {
            for row in col.iter() {
                for cell in row.iter() {
                    buffer.push(cell);
                    if buffer.len() >= 1000 {
                        Self::insert_batch(&tx, run_id, &buffer)?;
                        buffer.clear();
                    }
                }
            }
        }

        if !buffer.is_empty() {
            Self::insert_batch(&tx, run_id, &buffer)?;
        }

        tx.commit()?;

        Ok(())
    }

    fn record_timestep_summary(&mut self, timestep: usize, step_duration_myr: f64, grid: &Vec<Vec<Vec<Cell>>>, run_id: i64, scale_factor: f64, total_matter: f64) -> Result<()> {
        let mut total_rip_strength = 0.0;
        let mut black_hole_count: i64 = 0;
        let mut smbh_count: i64 = 0;
        let mut cell_count = 0;
        let mut total_gravity_magnitude = 0.0;

        for col in grid {
            for row in col {
                for cell in row {
                    total_rip_strength += cell.rip_strength;

                    let gm = (cell.gravity_x.powi(2) + cell.gravity_y.powi(2) + cell.gravity_z.powi(2)).sqrt();
                    total_gravity_magnitude += gm;

                    if cell.is_black_hole {
                        black_hole_count += 1;
                    }

                    if cell.is_supermassive {
                        smbh_count += 1;
                    }

                    cell_count += 1;
                }
            }
        }
        let avg_gravity_magnitude = total_gravity_magnitude / cell_count as f64;
        let avg_rip_strength = finite_or_zero(total_rip_strength / cell_count.max(1) as f64);
        let avg_scale_factor = finite_or_zero(scale_factor);

        let time_myr = timestep as f64 * step_duration_myr;

        self.conn.execute(
            "insert into timestep_summary (timestep, time_myr, rip_strength_avg, scale_factor, run_id, total_matter, black_hole_count, gravity_magnitude_avg, smbh_count)
				 values (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                timestep as i64,
                time_myr,
                avg_rip_strength,
                avg_scale_factor,
                run_id,
                total_matter,
                black_hole_count,
                avg_gravity_magnitude,
                smbh_count
            ],
        )?;

        Ok(())
    }

    fn get_or_insert_cell_position(&mut self, col: usize, row: usize) -> CellPosition {
        let mut stmt = self
            .conn
            .prepare("select cell_position_id from cell_position where col = ?1 and row = ?2")
            .expect("Failed to prepare select");

        if let Ok(row_id) = stmt.query_row(params![col, row], |row| row.get(0)) {
            return CellPosition { cell_position_id: row_id, col, row };
        }

        self.conn
            .execute("insert into cell_position (col, row) values (?1, ?2)", params![col, row])
            .expect("Failed to insert cell_position");

        let id = self.conn.last_insert_rowid();

        CellPosition { cell_position_id: id, col, row }
    }

    fn log_message(&mut self, run_id: i64, module: &str, level: LogLevel, message: &str) -> rusqlite::Result<()> {
        let timestamp = get_current_date_time();

        let level_str = match level {
            LogLevel::Debug => "debug",
            LogLevel::Info => "info",
            LogLevel::Warning => "warning",
            LogLevel::Error => "error",
        };

        dbg!("[{}] [{}] {}: {}", timestamp, level_str, module, message);

        self.conn.execute(
            "insert into log (run_id, timestamp, module, level, message) values (?1, ?2, ?3, ?4, ?5)",
            (run_id, timestamp, module, level_str, message),
        )?;

        return Ok(());
    }
}

fn get_current_date_time() -> f64 {
    let timestamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis() as f64;
    timestamp
}

impl SqliteProvider {
    fn insert_batch(tx: &rusqlite::Transaction, run_id: i64, cells: &[&Cell]) -> Result<()> {
        let mut stmt = tx.prepare(
            "insert into cell (
						run_id, cell_position_id, timestep, curvature,
						matter_density, is_black_hole, rip_strength,
						black_hole_id, layer, scale_factor,
						gravity_x, gravity_y, gravity_z, dimple_strength, is_lensing_candidate,
						is_supermassive, mass, smbh_rip_contribution, is_rip_induced
				) values (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19)",
        )?;
        for cell in cells {
            stmt.execute(params![
                run_id,                           // 01
                cell.position.cell_position_id,   // 02
                cell.timestep,                    // 03
                cell.curvature,                   // 04
                cell.matter_density,              // 05
                cell.is_black_hole,               // 06
                cell.rip_strength,                // 07
                cell.black_hole_id,               // 08
                cell.layer,                       // 09
                cell.scale_factor,                // 10
                cell.gravity_x,                   // 11
                cell.gravity_y,                   // 12
                cell.gravity_z,                   // 13
                cell.dimple_strength,             // 14
                cell.is_lensing_candidate as i32, // 15
                cell.is_supermassive as i32,      // 16
                cell.mass,                        // 17
                cell.smbh_rip_contribution,       // 18
                cell.is_rip_induced,              // 19
            ])?;
        }
        Ok(())
    }
}

#[inline]
fn finite_or_zero(v: f64) -> f64 {
    if v.is_finite() { v } else { 0.0 }
}

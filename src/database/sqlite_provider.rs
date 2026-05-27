use crate::database::db_provider::DbProvider;
use crate::database::entities::cell::Cell;
use crate::database::entities::cell_position::CellPosition;
use crate::database::entities::inflation_snapshot::InflationSnapshot;
use crate::database::entities::structure_particle::StructureParticle;
use crate::enums::LogLevel;
use rusqlite::{Connection, Result, params};

pub struct SqliteProvider {
    pub conn: Connection,
}

impl DbProvider for SqliteProvider {
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

    fn save_all_cells(&mut self, grid: &mut Vec<Vec<Vec<Cell>>>) -> Result<()> {
        let tx = self.conn.transaction()?;
        let mut buffer = Vec::with_capacity(1000);

        for col in grid.iter() {
            for row in col.iter() {
                for cell in row.iter() {
                    // progress_bar.inc(1);
                    buffer.push(cell);
                    if buffer.len() >= 1000 {
                        Self::insert_batch(&tx, &buffer)?;
                        buffer.clear();
                    }
                }
            }
        }
        if !buffer.is_empty() {
            Self::insert_batch(&tx, &buffer)?;
        }
        tx.commit()?;
        Ok(())
    }

    fn load_inflation_snapshots(&self) -> Result<Vec<InflationSnapshot>> {
        let mut stmt = self.conn.prepare(
            "select timestep,
                    avg(scale_factor) as scale_factor,
                    avg(rip_strength) as rip_strength,
                    avg(matter_density) as average_density,
                    avg(curvature) as average_curvature,
                    sum(case when is_black_hole then 1 else 0 end) as black_hole_count
             from cell
             group by timestep
             order by timestep",
        )?;

        let rows = stmt.query_map([], |row| {
            Ok(InflationSnapshot {
                timestep: row.get(0)?,
                scale_factor: row.get(1)?,
                rip_strength: row.get(2)?,
                average_density: row.get(3)?,
                average_curvature: row.get(4)?,
                black_hole_count: row.get(5)?,
                gravity_well_sum: row.get(6)?,
            })
        })?;

        let mut snapshots = Vec::new();
        for snapshot in rows {
            snapshots.push(snapshot?);
        }

        Ok(snapshots)
    }

    fn record_rip_field_summary(
        &mut self,
        timestep: usize,
        step_duration_myr: f64,
        grid: &Vec<Vec<Vec<Cell>>>,
    ) -> Result<()> {
        let mut total_rip_strength = 0.0;
        let mut total_scale_factor = 0.0;
        let mut cell_count = 0;

        for col in grid {
            for row in col {
                for cell in row {
                    total_rip_strength += cell.rip_strength;
                    total_scale_factor += cell.scale_factor;
                    cell_count += 1;
                }
            }
        }

        let avg_rip_strength = total_rip_strength / cell_count as f64;
        let avg_scale_factor = total_scale_factor / cell_count as f64;
        let time_myr = timestep as f64 * step_duration_myr;

        self.conn.execute(
            "insert into rip_field_summary (timestep, time_myr, rip_strength_avg, scale_factor_avg)
         values (?1, ?2, ?3, ?4)",
            params![
                timestep as i64,
                time_myr,
                avg_rip_strength,
                avg_scale_factor
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
            return CellPosition {
                cell_position_id: row_id,
                col,
                row,
            };
        }

        self.conn
            .execute(
                "insert into cell_position (col, row) values (?1, ?2)",
                params![col, row],
            )
            .expect("Failed to insert cell_position");

        let id = self.conn.last_insert_rowid();

        CellPosition {
            cell_position_id: id,
            col,
            row,
        }
    }

    fn log_message(
        &mut self,
        module: &str,
        level: LogLevel,
        message: &str,
    ) -> rusqlite::Result<()> {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as f64;

        let level_str = match level {
            LogLevel::Debug => "debug",
            LogLevel::Info => "info",
            LogLevel::Warning => "warning",
            LogLevel::Error => "error",
        };

        dbg!("[{}] [{}] {}: {}", timestamp, level_str, module, message);

        self.conn.execute(
            "insert into log (timestamp, module, level, message) values (?1, ?2, ?3, ?4)",
            (timestamp, module, level_str, message),
        )?;

        return Ok(());
    }
}

impl SqliteProvider {
    fn insert_batch(tx: &rusqlite::Transaction, cells: &[&Cell]) -> Result<()> {
        let mut stmt = tx.prepare(
            "
        insert into cell (
            cell_position_id, timestep, curvature,
            matter_density, is_black_hole, rip_strength,
            black_hole_id, layer, scale_factor,
            gravity_x, gravity_y, gravity_z,  dimple_strength, is_lensing_candidate,
            is_supermassive, mass, smbh_rip_contribution, is_rip_induced
        ) values (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18)
    ",
        )?;
        for cell in cells {
            stmt.execute(params![
                cell.position.cell_position_id,   // 01
                cell.timestep,                    // 02
                cell.curvature,                   // 03
                cell.matter_density,              // 04
                cell.is_black_hole,               // 05
                cell.rip_strength,                // 06
                cell.black_hole_id,               // 07
                cell.layer,                       // 08
                cell.scale_factor,                // 09
                cell.gravity_x,                   // 10
                cell.gravity_y,                   // 11
                cell.gravity_z,                   // 12
                cell.dimple_strength,             // 13
                cell.is_lensing_candidate as i32, // 14
                cell.is_supermassive as i32,      // 15
                cell.mass,                        // 16
                cell.smbh_rip_contribution,       // 17
                cell.is_black_hole                // 18
            ])?;
        }
        return Ok(());
    }
}

use rusqlite::{Connection, Result};
use std::fs;
use std::path::Path;

/// Copies the template DB and opens a new connection.
/// If `force_reset` is true, the existing `rip_data.db` will be deleted.
/// Returns a Connection to `data/rip_data.db`.
pub fn setup_database(force_reset: bool) -> Result<Connection> {
    let template = Path::new(env!("CARGO_MANIFEST_DIR")).join("data/template.db");
    let db = Path::new(env!("CARGO_MANIFEST_DIR")).join("data/rip_data.db");
    let shm = Path::new(env!("CARGO_MANIFEST_DIR")).join("data/rip_data.db-shm");
    let wal = Path::new(env!("CARGO_MANIFEST_DIR")).join("data/rip_data.db-wal");

    if force_reset && db.exists() {
        fs::remove_file(&db).unwrap();
        if shm.exists() {
            fs::remove_file(&shm).unwrap();
        }
        if wal.exists() {
            fs::remove_file(&wal).unwrap();
        }
    }

    if !db.exists() {
        fs::copy(&template, &db).unwrap();
    }

    let conn = Connection::open(db)?;
    conn.pragma_update(None, "journal_mode", &"WAL")?;

    // Optional: uncomment this for max speed with less durability
    conn.pragma_update(None, "synchronous", &"OFF")?;

    Ok(conn)
}

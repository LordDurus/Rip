use rusqlite::{Connection, Result};
use std::fs;
use std::path::Path;

/// Copies the template DB and opens a new connection.
/// If `force_reset` is true, the existing `rip_data.db` will be deleted.
/// Returns a Connection to `data/rip_data.db`.
pub fn setup_database(force_reset: bool) -> Result<Connection> {
    let source = Path::new("../data/template.db");
    let target = Path::new("../data/rip_data.db");

    if force_reset && target.exists() {
        fs::remove_file(&target).unwrap();
    }

    if !target.exists() {
        fs::copy(&source, &target).unwrap();
    }

    let conn = Connection::open(target)?;
    conn.pragma_update(None, "journal_mode", &"WAL")?;

    // Optional: uncomment this for max speed with less durability
    conn.pragma_update(None, "synchronous", &"OFF")?;

    Ok(conn)
}

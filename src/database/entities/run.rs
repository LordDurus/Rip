#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct Run {
    pub run_id: i64,
    pub started_at: String,
    pub ended_at: Option<String>,
    pub status: String,
    pub seed: u64,
    pub notes: Option<String>,
}

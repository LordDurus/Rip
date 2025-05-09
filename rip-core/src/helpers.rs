use flate2::Compression;
use flate2::write::GzEncoder;
use std::fs::File;
use std::io::BufWriter;

/// Helper functions for simulation calculations.

/// Calculates exponential decay of a field.
pub fn exponential_decay(initial_value: f64, lambda: f64, time: f64) -> f64 {
    initial_value * (-lambda * time).exp()
}

/// Creates a buffered gzip writer for the given path.
pub fn create_gzip_writer(path: &str) -> BufWriter<GzEncoder<File>> {
    let path = std::path::Path::new(path);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).expect("Failed to create parent directories");
    }
    let file = File::create(path).expect("unable to create file");
    let encoder = GzEncoder::new(file, Compression::default());
    BufWriter::new(encoder)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exponential_decay_simple() {
        let initial = 100.0;
        let decay_rate = 1.0;
        let time = 1.0;
        let result = exponential_decay(initial, decay_rate, time);
        assert!((result - 36.7879).abs() < 0.0001);
    }

    #[test]
    fn test_exponential_decay_zero_time() {
        let initial = 100.0;
        let decay_rate = 5.0;
        let time = 0.0;
        let result = exponential_decay(initial, decay_rate, time);
        assert_eq!(result, 100.0);
    }
}

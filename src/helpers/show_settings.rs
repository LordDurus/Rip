use crate::AppSetting;
use colored::Colorize;

pub fn show_settings(app_settings: &AppSetting) {
    if !app_settings.quiet {
        println!("{}", "=== Simulation Configuration ===".blue());
        let map = serde_json::to_value(app_settings).unwrap();
        let obj = map.as_object().unwrap();
        for (key, val) in obj {
            let display = match val {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            println!("{}{} {}", key.to_uppercase().cyan(), ":".yellow(), display.cyan());
        }
        println!("{}", "===============================".blue());
    }
}

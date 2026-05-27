CREATE TABLE app_setting (
    app_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
	datatype TEXT NOT null defualt
('f64')	
);

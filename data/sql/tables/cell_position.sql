create table if not exists cell_position (
    cell_position_id integer primary key autoincrement,
    col integer not null,
    row integer not null
    unique(col, row)
);

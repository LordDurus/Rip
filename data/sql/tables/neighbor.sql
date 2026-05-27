create table neighbor (
  neighbor_id integer primary key autoincrement,
  cell_id integer not null,
  neighbor_cell_id integer not null,
  distance real not null,
  foreign key(cell_id) references cell(cell_id),
  foreign key(neighbor_cell_id) references cell(cell_id)
);

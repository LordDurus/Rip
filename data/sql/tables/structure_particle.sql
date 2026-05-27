create table structure_particle (
    structure_particle_id  integer primary key autoincrement,
    time real not null,
    rip_strength real not null,
    scale_factor real not null,
    position_x real not null,
    position_y real not null,
    position_z real not null,
    velocity_x real not null,
    velocity_y real not null,
    velocity_z real not null
);

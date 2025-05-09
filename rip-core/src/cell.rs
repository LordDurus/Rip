use serde::{Deserialize, Serialize};
/*
fn parse_neighbors<'de, D>(deserializer: D) -> Result<Vec<(usize, usize, usize)>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let s: String = Deserialize::deserialize(deserializer)?;
    if s.trim().is_empty() {
        return Ok(vec![]);
    }

    s.split(';')
        .map(|triple| {
            let parts: Vec<&str> = triple.split(',').collect();
            if parts.len() != 3 {
                return Err(serde::de::Error::custom("Expected 3 values per neighbor"));
            }
            let a = parts[0].parse().map_err(serde::de::Error::custom)?;
            let b = parts[1].parse().map_err(serde::de::Error::custom)?;
            let c = parts[2].parse().map_err(serde::de::Error::custom)?;
            Ok((a, b, c))
        })
        .collect()
}
*/

fn de_bool_from_int<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let v: u8 = serde::Deserialize::deserialize(deserializer)?;
    Ok(v != 0)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Cell {
    pub col: usize,
    pub row: usize,
    pub layer: usize,
    pub timestep: usize,
    pub rip_strength: f64,
    pub curvature: f64,
    pub matter_density: f64,
    pub matter_density_smoothed: f64,
    #[serde(deserialize_with = "de_bool_from_int")]
    pub is_black_hole: bool,
    pub black_hole_id: Option<u64>,
    // #[serde(deserialize_with = "parse_neighbors")]
    //#[serde(skip_deserializing, default)]
    #[serde(skip, default)]
    pub neighbors: Vec<(usize, usize, usize)>, // indices of neighboring cells
    pub gravity_well: f64,
}

impl Cell {
    pub fn new() -> Self {
        Self {
            col: 0,
            row: 0,
            layer: 0,
            timestep: 0,
            rip_strength: 0.0,
            curvature: 0.0,
            matter_density: 0.0,
            matter_density_smoothed: 0.0,
            is_black_hole: false,
            black_hole_id: None,
            neighbors: Vec::new(),
            gravity_well: 0.0,
        }
    }

    pub fn apply_gravity_interaction(&mut self) {
        self.matter_density += 0.05 * self.curvature;
        self.curvature += 0.005 * self.matter_density;
    }

    pub fn assign_neighbors(&mut self, max: usize) {
        self.neighbors.clear();
        let col = self.col as isize;
        let row = self.row as isize;
        let layer = self.layer as isize;

        for dx in [-1, 0, 1] {
            for dy in [-1, 0, 1] {
                for dz in [-1, 0, 1] {
                    if dx == 0 && dy == 0 && dz == 0 {
                        continue;
                    }
                    let nx = col + dx;
                    let ny = row + dy;
                    let nz = layer + dz;

                    if (0..max as isize).contains(&nx)
                        && (0..max as isize).contains(&ny)
                        && (0..max as isize).contains(&nz)
                    {
                        self.neighbors.push((nx as usize, ny as usize, nz as usize));
                    }
                }
            }
        }
    }
}

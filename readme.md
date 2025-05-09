# Rip Field Simulation

This project simulates the evolution of spacetime curvature and matter distribution under the influence of a rip field.

---

## Requirements

This project uses both Rust and Python components.

### 🦀 Rust

- Rust 1.70 or later recommended
- `cargo` to build and run
- Multi-crate workspace with `rip-core`, `rip-inf`, and `rip-de`

### 🐍 Python

Used for rendering and animating simulation output.

#### Required Modules

Install with:

```bash
pip install matplotlib pandas numpy scipy
```

Optionally:

```bash
pip install ffmpeg-python
```

> FFmpeg must also be installed on your system and available in the PATH for video + audio merging.

#### Optional CLI Tools

- `gifsicle` (for GIF optimization)
- `ffmpeg` (for merging video + audio tracks)

---

## Output Media

Simulations produce:

- `.csv.gz` files containing simulation output
- `.mp4` or `.gif` animations generated via Python scripts in the `assets/` or `scripts/` folder

See also:
- [`rip_field_math.md`](./rip_field_math.md)
- [`rip_field_inflation_to_structure.md`](./rip_field_inflation_to_structure.md)

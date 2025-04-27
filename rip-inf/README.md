# Rip Field Inflation Simulation

[![Rust](https://img.shields.io/badge/Rust-1.70%2B-orange)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Overview

This project simulates cosmic inflation driven by a decaying scalar "rip field." 
The rip field initially dominates the energy density, causing rapid exponential expansion of space. As the rip field decays exponentially, inflation ends and a normal expansion phase begins.

The simulation and visualization pipeline includes:
- **Rust simulation** to generate rip field decay and scale factor growth.
- **Python scripts** to plot results and create animations.

---

## Project Structure

```
/ (project root)
|-- src/                  # Rust source code for the simulation
|-- data/                 # Output CSV files (time, rip_strength, scale_factor)
|-- scripts/              # Python plotting and animation scripts
|-- assets/               # Saved plots and GIF animations
|-- README.md             # Project documentation
|-- paper.md              # Scientific writeup
```

---

## How to Run

### 1. Run the Simulation

```bash
cargo run
```

This creates `data/simulation.csv` containing:
- time
- rip_strength
- scale_factor

### 2. Generate Static Plot

```bash
python scripts/plot_simulation.py
```

Outputs:
- `assets/scale_factor_rip_plot_inflation_end.png`

**Description:**
Static plot showing scale factor and rip field strength versus time. A green dashed line marks where inflation ends.

### 3. Generate Animated Inflation

```bash
python scripts/animate_inflation.py
```

Outputs:
- `assets/inflation_animation.gif`

**Description:**
Animated GIF showing how the scale factor grows exponentially over time.

---

## Example Visualizations

### Static Plot

**File:** `assets/scale_factor_rip_plot_inflation_end.png`

Displays scale factor growth and rip strength decay on a log-log plot. Inflation end is clearly marked.

### Animation

**File:** `assets/inflation_animation.gif`

An animated view of rapid early-universe expansion as driven by the rip field.

---

## Requirements

- Rust and Cargo
- Python 3.x
- Python packages:

```bash
pip install pandas matplotlib pillow
```

---

## Future Work

- Animate rip field decay alongside scale factor.
- Explore varying decay rates (`lambda`).
- Add quantum fluctuation modeling.
- Simulate reheating phase after inflation.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

Open for scientific exploration and educational use.


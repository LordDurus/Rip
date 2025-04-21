# Rip Simulation

**Exploration of a Rip in spacetime causing Dark Energy**

This project simulates a theoretical model where **black holes induce rips in spacetime**, causing a net loss of mass-energy. These rips produce an **expanding tension field**, which may mimic the observed effects of **dark energy** — accelerating the expansion of the universe.

The goal is to test whether such rips, occurring over cosmological timescales, can generate an effective pressure similar to the cosmological constant in ΛCDM (Lambda Cold Dark Matter) models.

## 🔬 Concept

- Each galaxy hosts a supermassive black hole.
- As matter falls into the black hole, there's a chance it is permanently destroyed by a **rip** (instead of being stored behind the event horizon).
- The erasure of mass generates a **rip field**, which slowly accumulates across the universe.
- This field acts like a repulsive pressure and is compared against known dark energy behavior.

## 🧮 Features

- Galaxy simulation with mass inflow and black hole tracking
- Probabilistic rip events based on time and black hole size
- `rip_field` accumulator represents the outward tension effect
- CSV export of rip field over time
- Python script for visualizing against ΛCDM expectations

## 🛠️ Setup Instructions

### 📦 Prerequisites
- [Rust](https://www.rust-lang.org/tools/install)
- [Python 3.13+ (official build)](https://www.python.org/downloads/)
- Python packages: `matplotlib`, `pandas`

### 📁 Project Structure
```
Rip/
├── Scripts/
│   └── plot_rip_field.py
├── src/
│   └── main.rs
├── rip_output.csv (created by the simulation)
├── Cargo.toml
├── README.md
└── LICENSE
```

### 🧪 Running the Simulation

1. Build and run the simulation with Cargo:

```sh
cargo run
```

2. This will generate `rip_output.csv` in the project root.

### 📈 Visualizing Results

1. Navigate to the `Scripts` folder:

```sh
cd Scripts
```

2. Run the plot script:

```sh
python plot_rip_field.py
```

3. A window will open showing a graph comparing the simulated rip field to the expected ΛCDM dark energy level.

If you get an error about missing packages, install them with:
```sh
pip install matplotlib pandas
```

### 🧠 Notes for Review
- The shape of the rip curve is the key insight — slow rise, then acceleration around 5–7 billion years (mirroring cosmic expansion).
- This can be tuned using parameters in `main.rs` such as rip probability and destroyed mass.

## 📚 Future Goals

- Tune simulation to better match ΛCDM acceleration profile
- Explore feedback mechanisms and saturation models
- Add spatial rip propagation
- Compare to observational cosmology data (e.g., Planck, supernovae datasets)

## 🧠 Status
Early-stage prototype. Designed for conceptual exploration, not precision cosmology (yet).

---

Made with curiosity, by someone who doesn't like the idea of "nothing."


# Rip Field Model

This project explores a speculative cosmological model where dark energy is not a constant, but the result of cumulative mass-energy destruction via rips in spacetime. These rips originate near supermassive black holes and build a global tension field — the "rip field" — which drives universal expansion.

---

## 🌌 Features

- **Rust-based galaxy simulator** with configurable parameters
- Models mass infall and rip events per galaxy
- Tracks a global `rip_field` and exports results to CSV
- **Multithreaded simulations** across `NUM_RUNS`
- Visualized using Python (Matplotlib, Pandas)
- Outputs saved to the `assets/` folder for direct use in publications

---

## 📁 Project Structure

```
.
.
├── Cargo.toml
├── src/
│   ├── main.rs                      # Simulation entry
│   └── magic_numbers.rs             # Universal constants
├── data/                            # Output CSVs
├── assets/                          # Generated plots (PNG)
├── scripts/                         # Python visualizations
│   ├── plot_all.py
│   ├── plot_rip_field.py
│   ├── plot_rip_field_overlay.py
│   ├── plot_rip_field_second_derivative.py
│   ├── plot_rip_field_mean_std.py
│   ├── plot_rip_field_derivative.py
│   ├── plot_rip_field_fit.py
│	 ├── run_all_scripts.py               # Master script to generate all plots

```

---

## 📊 Visualizations

All plots are generated and saved to `assets/`.

| Plot                                | Description                              |
|-------------------------------------|------------------------------------------|
| `rip_field_overlay.png`             | All simulation runs overlaid             |
| `rip_field_mean_std.png`            | Mean + ±1 std deviation                  |
| `rip_field_derivative.png`          | First derivative (growth rate)           |
| `rip_field_all_normalized.png`      | Averaged & normalized vs ΛCDM reference  |

---

## 🚀 Quickstart

### 1. Build the Simulator
```sh
cargo build --release
```

### 2. Run the Simulation
```sh
cargo run --release
```

This will generate `run_0.csv` through `run_9.csv` in the `data/` folder.

### 3. Generate Plots
```sh
py run_all_scripts.py
```

---

## 🧪 Manual Plotting (optional)
Run any of the following from the `scripts/` folder:

```sh
py plot_rip_field_overlay.py          # Overlay of all runs
py plot_rip_field_mean_std.py         # Mean ± stddev
py plot_rip_field_derivative.py       # First derivative (growth rate)
py plot_all.py                        # Normalized overlay + ΛCDM reference
py plot_rip_field.py                  # Legacy or simple plot, useful for debug

---

## 📖 Paper

The scientific write-up is in [`paper.md`](paper.md) — ready for publication or preprint. All referenced figures are synced with the output from the latest scripts.

---

## 📜 License

MIT License — feel free to explore, fork, extend, or question the cosmos.

---

## 🙌 Credits

Created by Tom Rooker as a speculative and computational exploration of what might lie behind dark energy — with Rust, Python, and curiosity.

# Setup & Requirements

How to build and run the Rip simulation (Rust) and its visualization scripts (Python).

---

## Rust — the simulation

### Toolchain

Install Rust via [rustup](https://rustup.rs/). This provides `cargo` (build/run) and `rustc` (compiler).

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # Linux/macOS
# Windows: download and run rustup-init.exe from https://rustup.rs/
```

Verify:

```sh
cargo --version
rustc --version
```

### Edition

The project uses Rust **edition 2024**, which requires a recent toolchain. Run `rustup update` if `cargo build` reports an unsupported edition.

### Crate dependencies

These are declared in `Cargo.toml` and fetched automatically on first `cargo build`. Listed here for reference:

| Crate | Version | Purpose |
|-------|---------|---------|
| `rusqlite` | 0.35.0 | SQLite access (settings, cells, timestep summaries) |
| `rustfft` | 6.2 | FFT for the Poisson gravity solver |
| `num-complex` | 0.4 | Complex numbers for FFT input/output |
| `rayon` | 1.8 | Data parallelism across the grid (24-thread runs) |
| `serde` | 1.0 | Settings serialization (`derive` feature) |
| `serde_json` | 1.0 | JSON settings display |
| `noise` | 0.9 | Perlin noise for initial curvature/density seeding |
| `rand` | 0.8 | Random seeding and SMBH formation probability rolls |
| `flate2` | 1.0 | Compression (`rust_backend` feature) |
| `indicatif` | 0.17 | Progress bars during long runs |
| `ctrlc` | 3 | Graceful Ctrl-C handling (clean run shutdown) |
| `crossterm` | 0.27 | Terminal control |
| `colored` | 3.1.1 | Colored terminal output |

### Build & run

```sh
cargo build --release    # optimized build (use for real runs — far faster)
cargo run --release       # build + run
```

Debug builds (`cargo build` with no flag) compile faster but run much slower; use release for any multi-thousand-timestep run.

---

## Python — the visualization scripts

The plotting scripts live in `scripts/` and read from the SQLite DB the simulation writes.

### Python version

Python 3.10+ recommended (developed against 3.13).

### Required packages

Install the third-party packages with pip:

```sh
pip install pandas numpy matplotlib plotly scipy kaleido
```

| Package | Used by | Purpose |
|---------|---------|---------|
| `pandas` | all plot scripts | DataFrame loading from SQLite |
| `numpy` | all plot scripts | Array math, percentiles, FFT power spectra |
| `matplotlib` | `plot_cmb.py`, `plot_structure.py`, `plot_matter.py`, `plot_inflation.py` | 2D plots and projections |
| `plotly` | `plot_3d.py` | Interactive 3D structure (HTML output) |
| `scipy` | `plot_structure.py` | `scipy.ndimage.label` for connected-component analysis |
| `kaleido` | `plot_3d.py` | Static PNG export from Plotly (`fig.write_image`) |

Standard-library modules used (no install needed): `argparse`, `sqlite3`, `shutil`, `subprocess`, `pathlib`.

### Optional external tool

- **`optipng`** — PNG size optimization. The scripts call `optipng.exe` if it is on `PATH` and silently skip optimization if it is not. Not required to produce plots.

---

## Running the plots

Scripts accept `--run-id` (defaults to the most recent completed run) and, where applicable, `--timestep`. `plot.bat` wraps the common invocations and accepts optional `run_id` and `timestep` arguments.

```sh
py plot_matter.py --run-id 1
py plot_3d.py --run-id 1 --timestep 2000 --no-png   # interactive HTML, skip slow PNG render
```

`plot_3d.py` flags:
- `--no-png` — skip the kaleido PNG render (faster; HTML only)
- `--no-html` — PNG only
- `--density-percentile` — node threshold (default 80)
- `--filament-low-percentile` — filament lower bound (default 50)

---

## Directory layout

- `data/rip_data.db` — SQLite database (settings, cells, timestep summaries)
- `output/` — generated plots (PNG/HTML)
- `scripts/` — Python visualization scripts
- `docs/` — `decisions.md`, `RESULTS.md`
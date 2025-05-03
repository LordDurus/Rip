import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import shutil
import subprocess
from datetime import datetime

def plot_phase(df, label, color):
    """Plot a simulation phase (inflation or dark energy)."""
    plt.plot(
        df['time'],
        df['scale_factor'],
        label=label,
        color=color
    )

# Load inflation data
inflation_df = pd.read_csv('../rip-inf/data/simulation.csv')

# Load dark energy data
dark_energy_files = sorted(glob.glob('../rip-de/data/run_*.csv'))
if not dark_energy_files:
    raise FileNotFoundError("No run_*.csv files found in rip-de/data/")
latest_dark_energy_file = dark_energy_files[-1]
dark_energy_df = pd.read_csv(latest_dark_energy_file)

# Rename dark energy 'time_myr' -> 'time'
dark_energy_df.rename(columns={'time_myr': 'time'}, inplace=True)

# Create figure
plt.figure(figsize=(10, 6))

# Plot phases using the helper function
plot_phase(inflation_df, 'Inflation Phase', 'blue')
plot_phase(dark_energy_df, 'Dark Energy Phase', 'red')

# Formatting
plt.yscale('log')
plt.xlabel('Time (simulation units or Myr)')
plt.ylabel('Scale Factor (log scale)')
plt.title('Combined Scale Factor: Inflation and Dark Energy')
plt.grid(True, which='both', linestyle='--', alpha=0.7)
plt.legend()

# Save plots
output_file = "../assets/combined_scale_factor_plot.png"

if shutil.which('optipng.exe'):
	try:
		subprocess.run(['optipng.exe', '-o7', output_file], check=True)            
	except subprocess.CalledProcessError as e:
		print(f"optipng failed: {e}")
else:
	print("optipng not found in PATH; skipping PNG optimization.")

print(f"Saved plot: {output_file}")

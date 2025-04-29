# scripts/create_combined_animation.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
import subprocess

# ---------- Load data ----------

# Load inflation data
inflation_df = pd.read_csv('rip-inf/data/simulation.csv')
inflation_df['time'] = inflation_df.index * 0.01  # Assume TIME_STEP=0.01 units for inflation

# Load dark energy data
import glob
dark_energy_files = sorted(glob.glob('rip-de/data/run_*.csv'))
if not dark_energy_files:
    raise FileNotFoundError("No run_*.csv files found in rip-de/data/")
latest_de_file = dark_energy_files[-1]
dark_energy_df = pd.read_csv(latest_de_file)
dark_energy_df.rename(columns={'time_myr': 'time'}, inplace=True)

# Shift dark energy time to start after inflation
inflation_end_time = inflation_df['time'].iloc[-1]
dark_energy_df['time'] += inflation_end_time + 0.1  # small gap to separate phases

# Combine
combined_time = np.concatenate([inflation_df['time'].values, dark_energy_df['time'].values])
combined_scale = np.concatenate([inflation_df['scale_factor'].values, dark_energy_df['scale_factor'].values])

# ---------- Animation Setup ----------

fig, ax = plt.subplots(figsize=(12, 7))
ax.set_yscale('log')
ax.set_xlabel('Time (Simulation Units / Myr)')
ax.set_ylabel('Scale Factor (log scale)')
ax.set_title('Combined Scale Factor Evolution')
ax.grid(True, which='both', linestyle='--', alpha=0.7)

line, = ax.plot([], [], lw=2)

label_text = ax.text(0.05, 0.95, '', transform=ax.transAxes, fontsize=16,
                     verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

ax.set_xlim(combined_time.min(), combined_time.max())
ax.set_ylim(1e0, combined_scale.max()*1.5)

# ---------- Define color transition ----------
def get_color(t_normalized):
    """Blend from blue to red."""
    r = t_normalized  # Red increases over time
    g = max(0.3, 1.0 - t_normalized)  # Green fades a bit
    b = 1.0 - t_normalized  # Blue decreases
    return (r, g, b)

# ---------- Define dynamic label ----------
def get_phase_label(current_time):
    if current_time < inflation_end_time:
        return "Inflation Phase"
    elif current_time < inflation_end_time + 5000:
        return "Matter Domination Phase"
    else:
        return "Dark Energy Domination"

# ---------- Animation function ----------
def animate(i):
    n_points = len(combined_time)
    idx = int(i * n_points / frames)

    if idx < 2:
        # Early startup
        placeholder_x = [combined_time[0], combined_time[1]]
        placeholder_y = [combined_scale[0], combined_scale[1]]
        line.set_data(placeholder_x, placeholder_y)
        line.set_color((0.7, 0.7, 0.7))
    else:
        # Normal drawing
        x = combined_time[:idx]
        y = combined_scale[:idx]

        t_normalized = idx / n_points
        line.set_data(x, y)
        line.set_color(get_color(t_normalized))

    # Label logic (separate and clean)
    fade_frames = 10
    if i < fade_frames:
        label_text.set_alpha(1.0 - (i / fade_frames))
        label_text.set_text("Starting simulation...")
    else:
        label_text.set_alpha(1.0)
        label_text.set_text(get_phase_label(combined_time[idx-1]))

    return line, label_text


# ---------- Create the animation ----------
frames = len(combined_time)
# frames = 500
ani = animation.FuncAnimation(
    fig, animate, frames=frames, interval=20, blit=False
)

# Save animation
gif_path = 'assets/combined_scale_factor_animation.gif'
ani.save(gif_path, writer='pillow', fps=30)
print(f"Animation saved to {gif_path}")

# ---------- Shrink with gifsicle if available ----------
try:
    subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", gif_path, "-o", gif_path], check=True)
    print("GIF compressed successfully using gifsicle!")
except FileNotFoundError:
    print("gifsicle not found. Skipping compression. Install gifsicle to optimize GIF size.")

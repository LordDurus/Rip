import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import subprocess

# Paths
data_dir = os.path.join(os.path.dirname(__file__), "../data")
assets_dir = os.path.join(os.path.dirname(__file__), "../assets")
csv_files = sorted(glob.glob(os.path.join(data_dir, "run*.csv")))

# Load and normalize data
dataframes = []
for file in csv_files:
    df = pd.read_csv(file)
    df = df[["time_myr", "rip_strength"]].copy()
    label = os.path.splitext(os.path.basename(file))[0]
    df.rename(columns={"rip_strength": label}, inplace=True)
    df.set_index("time_myr", inplace=True)
    dataframes.append(df)

combined = pd.concat(dataframes, axis=1)
combined["average"] = combined.mean(axis=1)
combined["min"] = combined.min(axis=1)
combined["max"] = combined.max(axis=1)

# Normalize to ΛCDM
lcdm_value = 7e-27
normalizer = combined["average"].max()
combined_normalized = combined * (lcdm_value / normalizer)
combined_normalized = combined_normalized.reset_index().rename(columns={"time_myr": "time"}).sort_values("time")

# Setup frames
n = len(combined_normalized)
frame_count = 300
interp_indices = np.linspace(0, 1, frame_count) ** 1.8
interp_indices = (interp_indices * (n - 1)).astype(int)
frames = sorted(set(interp_indices)) + [n - 1] * 20  # pause at end

# Plot setup
fig, ax = plt.subplots(figsize=(10, 6))
ax.set_xlabel("Time (Million Years)")
ax.set_ylabel("Energy Density (kg/m³, normalized)")
ax.set_title("Rip Field vs. Cosmic Time (Multiple Runs)")
ax.set_xlim(combined_normalized["time"].min(), combined_normalized["time"].max())
ax.set_ylim(0, combined_normalized["max"].max() * 1.05)
ax.grid(True)

# Plot lines for a few sample runs only (reduce legend clutter)
sample_labels = [c for c in combined.columns if c.startswith("run_")]
shown_labels = [lbl for i, lbl in enumerate(sample_labels) if i in (0, 1, 9, len(sample_labels)-1)]
run_lines = []
for label in sample_labels:
    show_label = label in shown_labels
    line, = ax.plot([], [], alpha=0.4, label=label if show_label else None)
    run_lines.append(line)

# Animated elements
avg_line, = ax.plot([], [], color="blue", linewidth=2, label="Average Rip Field")
lcdm_line = ax.axhline(y=lcdm_value, color='red', linestyle='--', label="ΛCDM Dark Energy Density")
lcdm_line.set_visible(False)
envelope_fill = [None]

ax.legend(loc='lower right', fontsize='small', frameon=True)

# Animation function
def update(frame_idx):
    sub = combined_normalized.iloc[:frame_idx+1]

    for i, label in enumerate(sample_labels):
        y = sub[label]
        run_lines[i].set_data(sub["time"], y)

    avg_line.set_data(sub["time"], sub["average"])

    if frame_idx == n - 1:
        if envelope_fill[0]:
            envelope_fill[0].remove()
        envelope_fill[0] = ax.fill_between(
            combined_normalized["time"],
            combined_normalized["min"],
            combined_normalized["max"],
            color="blue",
            alpha=0.15,
            label="Envelope (min/max)"
        )
        lcdm_line.set_visible(True)

    return run_lines + [avg_line, lcdm_line]

# Animate
ani = animation.FuncAnimation(fig, update, frames=frames, interval=30, blit=False)

# Save
gif_path = os.path.join(assets_dir, "../assets/rip_field_summary_animation.gif")
ani.save(gif_path, writer='pillow', fps=25)
print(f"Saved animation: {gif_path}")

# Compress (optional)
try:
    subprocess.run(["gifsicle", "-O3", "--colors", "256", gif_path, "-o", gif_path], check=True)
    print("Compressed with gifsicle")
except FileNotFoundError:
    print("gifsicle not found; skipping compression.")

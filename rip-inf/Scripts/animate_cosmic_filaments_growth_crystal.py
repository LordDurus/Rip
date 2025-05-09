
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import subprocess
from matplotlib.collections import LineCollection
from matplotlib.animation import FFMpegWriter

# --- config ---
csv_path = '../data/inflation.csv.gz'
layer_to_plot = 5
timesteps_to_use = 100
output_video = '../assets/filament_growth_crystal.mp4'
density_threshold = 0.01

# --- load data ---
print("Loading data...")
df = pd.read_csv(csv_path)

# --- grid size ---
cols = df['col'].max() + 1
rows = df['row'].max() + 1
max_timestep = df['timestep'].max()

# --- plot setup ---
plt.style.use('dark_background')
fig, ax = plt.subplots()
ax.set_facecolor('black')

# persistent line storage with age tracking
all_lines = {}

def update(frame):
    t = frame
    slice_df = df[(df['timestep'] == t) & (df['layer'] == layer_to_plot)]
    grid = np.zeros((rows, cols))

    for _, row in slice_df.iterrows():
        val = row['matter_density_smoothed']
        if val >= density_threshold:
            grid[int(row['row']), int(row['col'])] = 1

    for r in range(rows):
        for c in range(cols):
            if grid[r, c] == 1:
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and grid[nr, nc] == 1:
                            line = tuple(sorted([(c, r), (nc, nr)]))
                            if line not in all_lines:
                                all_lines[line] = t

    ax.clear()
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.set_facecolor('black')
    ax.set_title(f"Timestep {t}")

    if all_lines:
        lines = list(all_lines.keys())
        ages = np.array([t - ts for ts in all_lines.values()])
        norm = plt.Normalize(0, timesteps_to_use)
        glow_colors = plt.cm.winter(1 - norm(ages) ** 0.7)

        # Glow layer (soft blue, thick)
        glow = LineCollection(lines, colors=glow_colors, linewidths=2.5, alpha=0.3)
        # Core layer (sharp white, thin)
        crisp = LineCollection(lines, colors='white', linewidths=0.4, alpha=1.0)

        ax.add_collection(glow)
        ax.add_collection(crisp)

    # black holes as icy pulses
    bh = slice_df[slice_df['is_black_hole'] == 1]
    ax.scatter(bh['col'], bh['row'], s=4, c='aqua', alpha=0.6, marker='o')

    # optional: sparkle stars (static)
    if t == 0:
        np.random.seed(42)
        star_x = np.random.randint(0, cols, 60)
        star_y = np.random.randint(0, rows, 60)
        ax.scatter(star_x, star_y, s=0.5, c='lightcyan', alpha=0.2, marker='*')

    return []

# --- animation ---
print("Creating animation...")
writer = FFMpegWriter(fps=5, metadata=dict(artist='RipField'), bitrate=1800)
ani = animation.FuncAnimation(fig, update, frames=range(0, min(max_timestep + 1, timesteps_to_use)), blit=True)
ani.save(output_video, writer=writer)
print(f"Saved animation: {output_video}")

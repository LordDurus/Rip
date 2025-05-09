
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import subprocess
from matplotlib.collections import LineCollection

# --- config ---
csv_path = '../data/inflation.csv.gz'
layer_to_plot = 5
timesteps_to_use = 100
output_gif = '../assets/filament_growth_progressive.gif'
density_threshold = 0.01  # slower emergence

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

# persistent line storage (deduplicated)
#all_lines = set()
all_lines = {}

def update(frame):
    t = frame
    slice_df = df[(df['timestep'] == t) & (df['layer'] == layer_to_plot)]
    grid = np.zeros((rows, cols))

    for _, row in slice_df.iterrows():
        val = row['matter_density_smoothed']
        if val >= density_threshold:
            grid[int(row['row']), int(row['col'])] = 1

    # Only grow filaments every 2 timesteps
    if t % 2 == 0:
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
                                #all_lines.add(line)

    ax.clear()
    ax.set_title(f"Timestep {t}")
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.set_facecolor('black')

    if all_lines:
        lines = list(all_lines.keys())
        ages = np.array([t - ts for ts in all_lines.values()])
        norm = plt.Normalize(0, timesteps_to_use)
        colors = plt.cm.binary(1 - norm(ages))  # newer = whiter
        lc = LineCollection(lines, colors=colors, linewidths=0.4)
        ax.add_collection(lc)

    bh = slice_df[slice_df['is_black_hole'] == 1]
    ax.scatter(bh['col'], bh['row'], s=1, c='cyan', marker='o')

    return []

# --- animation ---
print("Creating animation...")
ani = animation.FuncAnimation(fig, update, frames=range(0, min(max_timestep + 1, timesteps_to_use)), blit=True)

# --- save gif ---
ani.save(output_gif, writer='pillow', fps=5)
print(f"Saved animation: {output_gif}")

# --- compress gif if gifsicle is installed ---
try:
    subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", output_gif, "-o", output_gif], check=True)
except FileNotFoundError:
    print("gifsicle not found. Skipping compression.")

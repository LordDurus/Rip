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
output_gif = '../assets/filament_growth.gif'
density_threshold = 0.005  # adjust to sharpen filament edges

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
grid = np.zeros((rows, cols))
im = ax.imshow(grid, cmap='binary', origin='lower', vmin=0, vmax=1)
scatter = ax.scatter([], [], s=1, c='cyan', marker='o')  # black hole overlay
ax.set_title('Filament Growth')

def update(frame):
	t = frame
	slice_df = df[(df['timestep'] == t) & (df['layer'] == layer_to_plot)]
	print(f"Timestep {t}: max density = {slice_df['matter_density_smoothed'].max():.5f}")
	grid = np.zeros((rows, cols))

	# mark dense cells
	for _, row in slice_df.iterrows():
		val = row['matter_density_smoothed']
		if val >= density_threshold:
			grid[int(row['row']), int(row['col'])] = 1

	# clear axes and reset background
	ax.clear()
	ax.set_title(f"Timestep {t}")
	ax.set_xlim(0, cols)
	ax.set_ylim(0, rows)
	ax.set_facecolor('black')

	# collect line segments between adjacent high-density cells
	lines = []
	for r in range(rows):
		for c in range(cols):
			if grid[r, c] == 1:
				for dr in [-1, 0, 1]:
					for dc in [-1, 0, 1]:
						if dr == 0 and dc == 0:
							continue
						nr, nc = r + dr, c + dc
						if 0 <= nr < rows and 0 <= nc < cols and grid[nr, nc] == 1:
							lines.append([(c, r), (nc, nr)])

	# draw filaments as white lines
	if lines:
		lc = LineCollection(lines, colors='white', linewidths=0.4)
		ax.add_collection(lc)

	# overlay black holes as cyan dots
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

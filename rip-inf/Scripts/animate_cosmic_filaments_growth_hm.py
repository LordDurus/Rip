import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import subprocess

# --- config ---
csv_path = '../data/inflation.csv.gz'
layer_to_plot = 5
timesteps_to_use = 100
output_gif = '../assets/filament_growth_hm.gif'
density_threshold = 0.03  # adjust to sharpen filament edges

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
	grid = np.zeros((rows, cols))

	for _, row in slice_df.iterrows():
		val = row['matter_density_smoothed']
		grid[int(row['row']), int(row['col'])] = 1 if val >= density_threshold else 0

	im.set_data(grid)
	ax.set_title(f'Timestep {t}')

	# update black holes
	bh = slice_df[slice_df['is_black_hole'] == 1]
	scatter.set_offsets(bh[['col', 'row']].values)

	return [im, scatter]

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

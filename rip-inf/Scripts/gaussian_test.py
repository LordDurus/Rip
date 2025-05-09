import pandas as pd
import numpy as np
import gzip
from scipy.ndimage import gaussian_filter
import matplotlib.pyplot as plt

# Load the CSV
with gzip.open("../data/inflation.csv.gz", "rt") as f:
	df = pd.read_csv(f)

# Create 3D grid of matter_density
grid_size = 64
density_grid = np.zeros((grid_size, grid_size, grid_size), dtype=np.float32)
for _, row in df[df["timestep"] == 99].iterrows():
	density_grid[int(row["col"]), int(row["row"]), int(row["layer"])] = row["matter_density"]

# Apply Gaussian smoothing
smoothed = gaussian_filter(density_grid, sigma=1.2)

# Plot middle Z slice
plt.imshow(smoothed[:, :, grid_size // 2], cmap="inferno")
plt.colorbar(label="Smoothed Density")
plt.title("2D Slice of Smoothed Density (Z=32)")
plt.show()

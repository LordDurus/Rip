import pandas as pd
import numpy as np
import gzip
from scipy.ndimage import gaussian_filter

# Parameters
CSV_IN = "../data/inflation.csv.gz"
CSV_OUT = "../data/inflation_smoothed.csv.gz"
GRID_SIZE = 64
SIGMA = 1.2

# Load full data
with gzip.open(CSV_IN, "rt") as f:
	df = pd.read_csv(f)

# Prepare output list
output = []

# Apply smoothing by timestep
for timestep in sorted(df["timestep"].unique()):
	slice_df = df[df["timestep"] == timestep].copy()
	grid = np.zeros((GRID_SIZE, GRID_SIZE, GRID_SIZE), dtype=np.float32)
	for _, row in slice_df.iterrows():
		grid[int(row["col"]), int(row["row"]), int(row["layer"])] = row["matter_density"]

	smoothed = gaussian_filter(grid, sigma=SIGMA)

	# Flatten smoothed grid and assign values back to rows
	slice_df["smoothed_density"] = [
		smoothed[int(c), int(r), int(l)]
		for c, r, l in zip(slice_df["col"], slice_df["row"], slice_df["layer"])
	]

	output.append(slice_df)

# Combine and save
full_df = pd.concat(output, ignore_index=True)
with gzip.open(CSV_OUT, "wt") as f:
	full_df.to_csv(f, index=False)

print(f"Smoothed file written to {CSV_OUT}")

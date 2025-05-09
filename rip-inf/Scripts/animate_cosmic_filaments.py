import pandas as pd
import gzip
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import subprocess

# Parameters
CSV_PATH = "../data/inflation.csv.gz"
OUTPUT_PATH = "../assets/cosmic_filaments.gif"
GRID_SIZE = 64
TIMESTEPS = 100
DENSITY_THRESHOLD = 0.001  # apply after smoothing
POINT_SIZE = 8
ALPHA = 0.6

# Load data
with gzip.open(CSV_PATH, "rt") as f:
	df = pd.read_csv(f)

# Normalize smoothed density
df["density_norm"] = df["matter_density_smoothed"] / df["matter_density_smoothed"].max()

# Organize by timestep
timesteps = sorted(df["timestep"].unique())
frames = [df[df["timestep"] == t] for t in timesteps]

# Set up figure
fig = plt.figure()
fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)
ax = fig.add_subplot(111, projection="3d")
ax.set_title("Cosmic Filament Formation")
ax.set_xlim(0, GRID_SIZE)
ax.set_ylim(0, GRID_SIZE)
ax.set_zlim(0, GRID_SIZE)
ax.set_xlabel("col")
ax.set_ylabel("row")
ax.set_zlabel("layer")

# Create fixed colorbar
norm = mcolors.Normalize(vmin=0, vmax=1)
mappable = cm.ScalarMappable(norm=norm, cmap="inferno")
mappable.set_array([])
cbar = plt.colorbar(mappable, ax=ax, fraction=0.03, pad=0.1)
cbar.set_label("Normalized Smoothed Density")

# Pre-populate scatter
sc = ax.scatter([], [], [], s=POINT_SIZE, alpha=ALPHA, c=[], cmap="inferno", vmin=0, vmax=1)

# Lock layout with frame 0
init = frames[0][frames[0]["density_norm"] > DENSITY_THRESHOLD]
sc._offsets3d = (init["col"], init["row"], init["layer"])
sc.set_array(init["density_norm"])
plt.draw()

# Animation function
def update(frame_idx):
	frame = frames[frame_idx]
	frame = frame[frame["density_norm"] > DENSITY_THRESHOLD]
	sc._offsets3d = (frame["col"], frame["row"], frame["layer"])
	sc.set_array(frame["density_norm"])
	return sc,

# Animate
ani = animation.FuncAnimation(fig, update, frames=len(frames), interval=100, blit=True)
ani.save(OUTPUT_PATH, writer="pillow")

# Optimize with gifsicle
try:
	subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", OUTPUT_PATH, "-o", OUTPUT_PATH], check=True)
except FileNotFoundError:
	print("gifsicle not found. Skipping compression.")

print(f"Saved animation to {OUTPUT_PATH}")

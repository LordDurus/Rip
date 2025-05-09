import pandas as pd
import gzip
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import subprocess
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# Parameters
CSV_PATH = "../data/inflation.csv.gz"
OUTPUT_PATH = "../assets/dimple_3d_animation.gif"
GRID_SIZE = 64
TIMESTEPS = 100
DOWNSAMPLE_FACTOR = 4
CURVATURE_THRESHOLD = 0.2  # normalized

# Load data
with gzip.open(CSV_PATH, "rt") as f:
	df = pd.read_csv(f)

# Normalize curvature
df["curvature_norm"] = df["curvature"] / df["curvature"].max()

# Group by timestep
timesteps = sorted(df["timestep"].unique())
frames = [df[df["timestep"] == t] for t in timesteps]

# Set up plot
fig = plt.figure()
fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)
ax = fig.add_subplot(111, projection='3d')
ax.set_title("Curvature Dimples")  # fixed title
ax.set_autoscale_on(False)  # prevent rescaling

sc = ax.scatter([], [], [], s=5, alpha=0.5, c=[], cmap="plasma", vmin=0, vmax=1)

# Fixed colorbar
norm = mcolors.Normalize(vmin=0, vmax=1)
mappable = cm.ScalarMappable(norm=norm, cmap="plasma")
mappable.set_array([])

cbar = plt.colorbar(mappable, ax=ax, fraction=0.03, pad=0.1)
cbar.set_label("Normalized Curvature")

ax.set_xlim(0, GRID_SIZE)
ax.set_ylim(0, GRID_SIZE)
ax.set_zlim(0, GRID_SIZE)
ax.set_xlabel("col")
ax.set_ylabel("row")
ax.set_zlabel("layer")

# Pre-draw layout to lock it in
update_frame = frames[0][(frames[0]["col"] % DOWNSAMPLE_FACTOR == 0) &
                         (frames[0]["row"] % DOWNSAMPLE_FACTOR == 0) &
                         (frames[0]["layer"] % DOWNSAMPLE_FACTOR == 0) &
                         (frames[0]["curvature_norm"] > CURVATURE_THRESHOLD)]
sc._offsets3d = (update_frame["col"], update_frame["row"], update_frame["layer"])
sc.set_array(update_frame["curvature_norm"])
plt.draw()

# Animation update
def update(frame_idx):
	frame = frames[frame_idx]
	frame = frame[(frame["col"] % DOWNSAMPLE_FACTOR == 0) &
	              (frame["row"] % DOWNSAMPLE_FACTOR == 0) &
	              (frame["layer"] % DOWNSAMPLE_FACTOR == 0)]
	frame = frame[frame["curvature_norm"] > CURVATURE_THRESHOLD]
	sc._offsets3d = (frame["col"], frame["row"], frame["layer"])
	sc.set_array(frame["curvature_norm"])
	return sc,

# Animate
ani = animation.FuncAnimation(fig, update, frames=len(frames), interval=100, blit=False)
ani.save(OUTPUT_PATH, writer="pillow")

# Optional: Compress with gifsicle
try:
	subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", OUTPUT_PATH, "-o", OUTPUT_PATH], check=True)
except FileNotFoundError:
	print("gifsicle not found. Skipping compression.")

print(f"Saved animation to {OUTPUT_PATH}")

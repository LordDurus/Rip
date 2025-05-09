import pandas as pd
import gzip
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import subprocess
from PIL import Image, ImageSequence

# Parameters
LAYER = 32         # slice index
OUTPUT_FILE = "../assets/curvature_animation.gif"
CSV_PATH = "../data/inflation.csv.gz"
GRID_SIZE = 64
TIMESTEPS = 100

# Load and parse data
with gzip.open(CSV_PATH, "rt") as f:
    df = pd.read_csv(f)

# Precompute frames
frames = []
for t in range(TIMESTEPS):
    start = t * GRID_SIZE**3
    end = (t + 1) * GRID_SIZE**3
    frame = df.iloc[start:end]
    frame = frame[frame["layer"] == LAYER]       
    curvature_grid = frame.pivot(index="row", columns="col", values="curvature").values
    bh_mask = frame["is_black_hole"].astype(bool).values.reshape((GRID_SIZE, GRID_SIZE))
    frames.append((curvature_grid, bh_mask))

# Plot setup
fig, ax = plt.subplots(figsize=(6, 6))
cax = ax.imshow(frames[0][0], cmap="plasma", vmin=0, vmax=0.3)
bh_overlay = ax.imshow(frames[0][1], cmap="Reds", alpha=0.4, vmin=0, vmax=1)
ax.set_title(f"Spacetime Curvature at Layer {LAYER}")
plt.axis("off")

# Update function
def update(i):
    cax.set_data(frames[i][0])
    bh_overlay.set_data(frames[i][1])
    ax.set_title(f"Timestep {i} - Layer {LAYER}")
    return [cax, bh_overlay]

# Animate
ani = animation.FuncAnimation(fig, update, frames=len(frames), interval=150, blit=True)
ani.save(OUTPUT_FILE, writer="pillow")

# ---------- Shrink with gifsicle if available ----------
try:
    subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", OUTPUT_FILE, "-o", OUTPUT_FILE], check=True)    
except FileNotFoundError:
    print("gifsicle not found. Skipping compression. Install gifsicle to optimize GIF size.")

# with Image.open(OUTPUT_FILE) as img:
#    frames = [
#        frame.copy().resize((256, 256), Image.LANCZOS)
#        for frame in ImageSequence.Iterator(img)
#    ]
#
    # Save optimized and resized version
#    frames[0].save(
#        OUTPUT_FILE,
#        save_all=True,
#        append_images=frames[1:],
#        loop=0,
#        duration=img.info.get("duration", 100),
#        optimize=True
#    )

print(f"Saved animation to {OUTPUT_FILE}")

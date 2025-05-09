import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import gzip
import os

# decompress if needed
if not os.path.exists('../data/structure.csv') and os.path.exists('../data/structure.csv.gz'):
    with gzip.open('../data/structure.csv.gz', 'rb') as f_in, open('../data/structure.csv', 'wb') as f_out:
        f_out.write(f_in.read())

# load data
df = pd.read_csv('../data/structure.csv', dtype={
    'time': float,
    'rip_strength': float,
    'scale_factor': float,
    'x': float,
    'y': float,
    'z': float,
    'vx': float,
    'vy': float,
    'vz': float
})

df['time'] = df['time'].round(6)
all_times = sorted(df['time'].unique())
times = all_times[::10]  # downsample every 10th timestep

# setup plot
fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(111, projection='3d')
sc = ax.scatter([], [], [], c=[], cmap='viridis', s=3, alpha=0.7)

ax.set_xlim(df['x'].min(), df['x'].max())
ax.set_ylim(df['y'].min(), df['y'].max())
ax.set_zlim(df['z'].min(), df['z'].max())
ax.set_title("Particle Motion Over Time")
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')

# update function
def update(frame_idx):
    t = times[frame_idx]
    frame_df = df[df['time'] == t]
    speed = np.sqrt(frame_df['vx']**2 + frame_df['vy']**2 + frame_df['vz']**2)

    sc._offsets3d = (frame_df['x'], frame_df['y'], frame_df['z'])
    sc.set_array(speed)
    ax.set_title(f"t = {t:.2f}")
    return sc,

# generate animation
ani = animation.FuncAnimation(fig, update, frames=len(times), interval=50, blit=False)

# save as gif
os.makedirs('../assets', exist_ok=True)
ani.save('../assets/particle_animation.gif', writer='pillow', fps=20)
print("3D particle GIF saved to assets/particle_animation.gif")

import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Load data
print("Loading data...")
df = pd.read_csv('../data/post.csv.gz')

# Filter to a specific timestep (e.g., first one)
timestep = 0
df_t0 = df[df['timestep'] == timestep]

# Filter by density threshold to reveal filament structure
density_threshold = 0.001
df_dense = df_t0[df_t0['matter_density_smoothed'] >= density_threshold]

# Prepare 3D plot
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')
ax.set_facecolor('black')
fig.patch.set_facecolor('black')

# Plot dense points as 3D scatter
sc = ax.scatter(
    df_dense['col'], df_dense['row'], df_dense['layer'],
    c=df_dense['matter_density_smoothed'],
    cmap='plasma', s=1, alpha=0.6
)

# Add colorbar
cb = fig.colorbar(sc, ax=ax, pad=0.1, fraction=0.02)
cb.set_label('Matter Density (smoothed)', color='white')
cb.ax.yaxis.set_tick_params(color='white')
plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='white')

# Aesthetics
ax.set_title(f'Post-Inflation Filaments (Timestep {timestep})', color='white')
ax.set_xlabel('col', color='white')
ax.set_ylabel('row', color='white')
ax.set_zlabel('layer', color='white')

for spine in ax.spines.values():
    spine.set_color('white')
ax.xaxis.label.set_color('white')
ax.yaxis.label.set_color('white')
ax.zaxis.label.set_color('white')
ax.tick_params(colors='white')

# Save
plt.tight_layout()
plt.savefig('../assets/post_filament_3d_t0.png', dpi=300, facecolor='black')
print("Saved to ../assets/post_filament_3d_t0.png")

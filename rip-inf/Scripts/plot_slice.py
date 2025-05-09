import pandas as pd
import matplotlib.pyplot as plt
import gzip

# Load the structure (inflation.rs) dataset
with gzip.open("../data/inflation.csv.gz", "rt") as f:
    df = pd.read_csv(f)

# Determine layer bounds
min_layer = df['layer'].min()
mid_layer = df['layer'].max() // 2
max_layer = df['layer'].max()

layers_to_plot = [min_layer, mid_layer, max_layer]

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

for i, layer in enumerate(layers_to_plot):
    slice_df = df[df['layer'] == layer]
    curv_matrix = slice_df.groupby(['row', 'col'])['curvature'].mean().unstack()

    im = axes[i].imshow(curv_matrix, cmap='plasma', origin='lower', vmin=0, vmax=df['curvature'].max())
    axes[i].set_title(f"Layer {layer}")
    axes[i].set_xlabel("col")
    axes[i].set_ylabel("row")

fig.colorbar(im, ax=axes.ravel().tolist(), label="Curvature")
plt.suptitle("Curvature Slices at Layers 0, Mid, Max")
plt.savefig("../assets/curvature_multi_slice.png", dpi=300)

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

# Directory that contains rip_output CSVs
data_dir = os.path.join(os.path.dirname(__file__), "../data")
assets_dir = os.path.join(os.path.dirname(__file__), "../assets")
data_files = glob.glob(os.path.join(data_dir, "run*.csv"))

# Storage for all runs
dataframes = []

for file in data_files:
    df = pd.read_csv(file)

    # Use only time_myr and rip_strength
    df = df[["time_myr", "rip_strength"]].copy()

    # Label each column with its filename (e.g., run_0)
    label = os.path.splitext(os.path.basename(file))[0]
    df.rename(columns={"rip_strength": label}, inplace=True)

    # Index by time and store
    df.set_index("time_myr", inplace=True)
    dataframes.append(df)


combined = pd.concat(dataframes, axis=1)
combined["average"] = combined.mean(axis=1)
combined["min"] = combined.min(axis=1)
combined["max"] = combined.max(axis=1)

# Normalize
lcdm_value = 7e-27
normalizer = combined["average"].max()
combined_normalized = combined * (lcdm_value / normalizer)

# Plot
plt.figure(figsize=(10, 6))

# Individual runs (label only first 3 and last to reduce clutter)
run_columns = [col for col in combined.columns if col not in ("average", "min", "max")]

for i, col in enumerate(run_columns):
    show_label = (i < 3 or i == len(run_columns) - 1)
    plt.plot(combined_normalized.index, combined_normalized[col], alpha=0.4,
             label=col if show_label else None)

# Envelope and average
plt.plot(combined_normalized.index, combined_normalized["average"], color="blue", linewidth=2, label="Average Rip Field")
plt.fill_between(
    combined_normalized.index,
    combined_normalized["min"],
    combined_normalized["max"],
    color="blue",
    alpha=0.15,
    label="Envelope (min/max)"
)

# ΛCDM reference line
plt.axhline(y=lcdm_value, color='red', linestyle='--', label="ΛCDM Dark Energy Density")

plt.title("Rip Field vs. Cosmic Time (Multiple Runs)")
plt.xlabel("Time (Million Years)")
plt.ylabel("Energy Density (kg/m³, normalized)")
plt.legend()
plt.grid(True)
#plt.tight_layout(rect=[0, 0, 1, 0.95])

# Save to assets
output_file = os.path.join(assets_dir, "rip_field_all_normalized.png")
plt.savefig(output_file, dpi=300)
print(f"Saved plot to: {output_file}")

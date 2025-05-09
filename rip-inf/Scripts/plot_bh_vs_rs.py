import pandas as pd
import gzip
import matplotlib.pyplot as plt

# Load data
with gzip.open("../data/inflation.csv.gz", "rt") as f:
	df = pd.read_csv(f)

# Group by timestep
grouped = df.groupby("timestep").agg({
    "rip_strength": "first",  # same for all rows in timestep
    "is_black_hole": "sum"    # count of black holes
}).reset_index()

# Plot
plt.figure(figsize=(10, 6))
plt.plot(grouped["rip_strength"], grouped["is_black_hole"], marker="o")
plt.xlabel("Rip Strength")
plt.ylabel("Number of Black Holes")
plt.title("Black Holes vs. Rip Strength")
plt.grid(True)
plt.tight_layout()
plt.savefig("../assets/black_holes_vs_rip_strength.png")

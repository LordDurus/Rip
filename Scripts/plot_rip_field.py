import pandas as pd
import matplotlib.pyplot as plt

# Load the rip field output file
df = pd.read_csv("../rip_output.csv")

# Normalize the rip field to match the observed dark energy density
lcdm_value = 7e-27  # kg/m^3
df["normalized_rip_field"] = df["rip_field"] * (lcdm_value / df["rip_field"].max())

# Plotting
plt.figure(figsize=(10, 6))
plt.plot(df["time_myr"], df["normalized_rip_field"], label="Simulated Rip Field (Normalized)", color="blue")
plt.axhline(y=lcdm_value, color='red', linestyle='--', label="ΛCDM Dark Energy Density")
plt.title("Rip Field vs. Cosmic Time")
plt.xlabel("Time (Million Years)")
plt.ylabel("Energy Density (kg/m³, normalized)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
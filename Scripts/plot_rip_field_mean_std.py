
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os

def plot_average_with_deviation(data_path, output_path):
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))
    rip_data = []

    for file_path in all_files:
        df = pd.read_csv(file_path)
        rip_data.append(df['rip_field'].values)

    rip_array = np.asarray(rip_data, dtype=np.float64)
    mean_rip = np.mean(rip_array, axis=0)
    std_rip = np.std(rip_array, axis=0)
    time = pd.read_csv(all_files[0])['time_myr'].values

    plt.figure(figsize=(12, 7))
    plt.plot(time, mean_rip, label="Mean Rip Field", color='black')
    plt.fill_between(time, mean_rip - std_rip, mean_rip + std_rip, color='gray', alpha=0.3, label="±1 Std Dev")

    plt.xlabel("Time (million years)")
    plt.ylabel("Rip Field (arbitrary units)")
    plt.title("Rip Field Evolution: Mean and Standard Deviation")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_file = os.path.join(output_path, "../assets/rip_field_mean_std.png")
    plt.savefig(output_file, dpi=300)
    print(f"Saved plot to: {output_file}")

if __name__ == "__main__":
    plot_average_with_deviation("../data", ".")

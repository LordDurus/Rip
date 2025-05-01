import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import shutil
import subprocess

def plot_average_with_deviation(data_path, output_path):
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))
    rip_data = []

    for file_path in all_files:
        df = pd.read_csv(file_path)
        rip_data.append(df['rip_strength'].values)

    rip_array = np.asarray(rip_data, dtype=np.float64)
    mean_rip = np.mean(rip_array, axis=0)
    std_rip = np.std(rip_array, axis=0)
    time = pd.read_csv(all_files[0])['time_myr'].values

    # Plot
    plt.figure(figsize=(12, 7))
    plt.plot(time, mean_rip, label="Mean Rip Field", color='black')
    plt.fill_between(time, mean_rip - std_rip, mean_rip + std_rip, color='gray', alpha=0.3, label="±1 Std Dev")
    plt.xlabel("Time (million years)")
    plt.ylabel("Rip Field (arbitrary units)")
    plt.title("Rip Field Evolution: Mean and Standard Deviation")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Save plot to assets
    output_file = os.path.join(output_path, "../assets/rip_field_mean_std.png")    
    plt.savefig(output_file, dpi=300)

    if shutil.which('optipng.exe'):
        try:
            subprocess.run(['optipng.exe', '-o7', output_file], check=True)            
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")


    print(f"Saved plot to: {output_file}")

    # ✅ Save the mean and std data to data/rip_field_mean_std.csv
    csv_path = os.path.join(data_path, "rip_field_mean_std.csv")
    df_out = pd.DataFrame({
        "time_myr": time,
        "rip_mean": mean_rip,
        "rip_std": std_rip
    })
    df_out.to_csv(csv_path, index=False)
    print(f"Saved data to: {csv_path}")

if __name__ == "__main__":
    plot_average_with_deviation("../data", ".")

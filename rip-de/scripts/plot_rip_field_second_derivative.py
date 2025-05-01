
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import shutil
import subprocess

def plot_second_derivative(data_path, output_path):
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))
    rip_data = []

    for file_path in all_files:
        df = pd.read_csv(file_path)
        rip_data.append(df['rip_strength'].values)

    rip_array = np.asarray(rip_data, dtype=np.float64)
    time = pd.read_csv(all_files[0])['time_myr'].values

    # First and second derivatives
    first_deriv = np.gradient(rip_array, axis=1)
    second_deriv = np.gradient(first_deriv, axis=1)

    mean_second = np.mean(second_deriv, axis=0)
    std_second = np.std(second_deriv, axis=0)

    # Plot
    plt.figure(figsize=(12, 7))
    plt.plot(time, mean_second, label="Mean d²(Rip Field)/dt²", color='darkred')
    plt.fill_between(time, mean_second - std_second, mean_second + std_second,
                     color='salmon', alpha=0.3, label="±1 Std Dev")

    plt.xlabel("Time (million years)")
    plt.ylabel("Acceleration of Rip Field")
    plt.title("Curvature of Rip Field (Second Derivative)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_file = os.path.join(output_path, "rip_field_second_derivative.png")
    plt.savefig(output_file, dpi=300)
    
    if shutil.which('optipng.exe'):
        try:
            subprocess.run(['optipng.exe', '-o7', output_file], check=True)            
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")

    
    print(f"Saved plot to: {output_file}")

if __name__ == "__main__":
    plot_second_derivative("../data", "../assets")

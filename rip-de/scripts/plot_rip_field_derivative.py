import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import shutil
import subprocess

def plot_rip_field_derivative(data_path, output_path):
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))
    derivatives = []

    for file_path in all_files:
        df = pd.read_csv(file_path)
        time = df['time_myr'].values
        rip = df['rip_strength'].values
        delta_rip = np.gradient(rip, time)  # first derivative
        derivatives.append(delta_rip)

    derivatives = np.array(derivatives)
    mean_derivative = np.mean(derivatives, axis=0)
    std_derivative = np.std(derivatives, axis=0)

    plt.figure(figsize=(12, 7))
    plt.plot(time, mean_derivative, label="Mean d(Rip Field)/dt", color='blue')
    plt.fill_between(time, mean_derivative - std_derivative, mean_derivative + std_derivative,
                     color='lightblue', alpha=0.3, label="±1 Std Dev")

    plt.xlabel("Time (million years)")
    plt.ylabel("Growth Rate of Rip Field")
    plt.title("Rate of Change of Rip Field (First Derivative)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_file = os.path.join(output_path, "../assets/rip_field_derivative.png")
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
    plot_rip_field_derivative("../data", ".")

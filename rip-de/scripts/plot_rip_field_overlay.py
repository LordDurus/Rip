
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import shutil
import subprocess

def plot_multi_run_overlay(data_path, output_path):
    plt.figure(figsize=(12, 7))
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))

    for file_path in all_files:
        df = pd.read_csv(file_path)
        time = df['time_myr']
        rip_field = df['rip_strength']
        label = os.path.basename(file_path)
        plt.plot(time, rip_field, label=label)

    plt.xlabel("Time (million years)")
    plt.ylabel("Rip Field (arbitrary units)")
    plt.title("Rip Field Evolution (Multi-run Overlay)")    
    plt.legend(fontsize='small', loc='upper left', ncol=2, title="Run Files")
    plt.grid(True)
    plt.tight_layout()
    output_file = os.path.join(output_path, "rip_field_overlay.png")
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
    plot_multi_run_overlay("../data", "../assets")

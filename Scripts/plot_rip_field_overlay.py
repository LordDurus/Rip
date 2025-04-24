
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os

def plot_multi_run_overlay(data_path, output_path):
    plt.figure(figsize=(12, 7))
    all_files = sorted(glob.glob(os.path.join(data_path, "run_*.csv")))

    for file_path in all_files:
        df = pd.read_csv(file_path)
        time = df['time_myr']
        rip_field = df['rip_field']
        label = os.path.basename(file_path)
        plt.plot(time, rip_field, label=label)

    plt.xlabel("Time (million years)")
    plt.ylabel("Rip Field (arbitrary units)")
    plt.title("Rip Field Evolution (Multi-run Overlay)")    
    plt.legend(fontsize='small', loc='upper left', ncol=2, title="Run Files")
    plt.grid(True)
    plt.tight_layout()
    output_file = os.path.join(output_path, "../assets/rip_field_overlay.png")
    plt.savefig(output_file, dpi=300)
    print(f"Saved plot to: {output_file}")

if __name__ == "__main__":
    plot_multi_run_overlay("data", ".")

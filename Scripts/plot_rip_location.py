import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import shutil
import subprocess
from pathlib import Path
from scipy.optimize import curve_fit

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rip_data.db"

def exp_model(t, a, b):
    return a * np.exp(b * t)

def plot_run(run_id, df):
    time = df['time_myr'].values
    rip = df['rip_strength_avg'].values

    try:
        popt, _ = curve_fit(exp_model, time, rip, maxfev=10000)
        fit_y = exp_model(time, *popt)
        label = f"run {run_id} (fit: a={popt[0]:.2e}, b={popt[1]:.2e})"
    except (RuntimeError, ValueError):
        fit_y = None
        label = f"run {run_id} (fit failed)"

    plt.plot(time, rip, label=label)
    if fit_y is not None:
        plt.plot(time, fit_y, linestyle='--', alpha=0.7)

def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT run_id, timestep, time_myr, rip_strength_avg
        FROM timestep_summary
        ORDER BY run_id, timestep
        """,
        conn,
    )
    conn.close()

    if df.empty:
        print("No timestep_summary rows found.")
        return

    print(f"Loaded {len(df)} summary rows across {df['run_id'].nunique()} runs.")

    plt.figure(figsize=(10, 6))
    for run_id, sub in df.groupby('run_id'):
        plot_run(run_id, sub)

    plt.xlabel('Time (million years)')
    plt.ylabel('Rip Field Average (arbitrary units)')
    plt.title('Rip Field Evolution')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_file = Path(__file__).resolve().parent.parent / "output" / "plot_rip_location.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=300)

    if shutil.which('optipng.exe'):
        try:
            subprocess.run(['optipng.exe', '-o7', str(output_file)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"optipng failed: {e}")
    else:
        print("optipng not found in PATH; skipping PNG optimization.")

    print(f"Saved plot: {output_file}")

if __name__ == "__main__":
    main()
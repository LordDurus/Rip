import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

# Define a model to fit: exponential as a starting point
def exp_model(t, a, b):
    return a * np.exp(b * t)

def load_and_plot(file_path):
    df = pd.read_csv(file_path)
    time = df['time_myr']
    rip = df['rip_field']

    # Fit exponential model
    try:
        popt, _ = curve_fit(exp_model, time, rip, maxfev=10000)
        fit_y = exp_model(time, *popt)
        label = f"{file_path} (fit: a={popt[0]:.2e}, b={popt[1]:.2e})"
    except RuntimeError:
        fit_y = None
        label = f"{file_path} (fit failed)"

    # Plot actual data
    plt.plot(time, rip, label=label)

    # Plot fitted curve if it succeeded
    if fit_y is not None:
        plt.plot(time, fit_y, linestyle='--', alpha=0.7)

def main():
    files = glob.glob('../data/run_*.csv')
    files.sort()

    plt.figure(figsize=(10, 6))
    for f in files:
        load_and_plot(f)

    plt.xlabel('Time (million years)')
    plt.ylabel('Rip Field (arbitrary units)')
    plt.title('Rip Field Evolution')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('../assets/rip_field_fit.png', dpi=300)
    plt.show()

if __name__ == "__main__":
    main()

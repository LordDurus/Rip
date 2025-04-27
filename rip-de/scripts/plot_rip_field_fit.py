# scripts/plot_rip_field_fit.py   ← NEW
import os, glob, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# ---------- logistic model ----------
def logistic(t, L, k, t0, C):
    """4-parameter logistic:  L / (1+exp(-k*(t - t0))) + C"""
    return L / (1 + np.exp(-k * (t - t0))) + C

# ---------- main ----------
def main():
    # 1. load mean rip-field
    run_files = sorted(glob.glob("../data/run_*.csv"))
    rip_runs  = [pd.read_csv(f)["rip_field"].values for f in run_files]
    rip_mean  = np.mean(rip_runs, axis=0)
    time_myr  = pd.read_csv(run_files[0])["time_myr"].values        # common x-axis

    # 2. fit only the rise section (≤ 7 Gyr)
    mask      = time_myr <= 7000                                     # 0–7 Gyr
    x_fit     = time_myr[mask]
    y_fit     = rip_mean[mask]

    # initial guesses:  L=max(y); k=1e-3; t0=half-rise; C=min(y)
    p0 = [y_fit.max(), 1e-3, x_fit[np.argmax(np.diff(y_fit))], y_fit.min()]
    popt, pcov = curve_fit(logistic, x_fit, y_fit, p0=p0, maxfev=20000)
    L,k,t0,C = popt

    # 3. plot
    plt.figure(figsize=(12,7))
    plt.plot(time_myr, rip_mean, label="Mean rip field", color="steelblue")
    plt.plot(time_myr, logistic(time_myr,*popt), "--", color="crimson",
             label=f"Logistic fit\nL={L:.3e}, k={k:.2e}, t0={t0:.0f} Myr")
    plt.xlabel("Time (million years)")
    plt.ylabel("Rip field (arbitrary units)")
    plt.title("Rip Field Evolution & Logistic Fit (0–7 Gyr calibrated)")
    plt.legend(); plt.grid(True); plt.tight_layout()

    os.makedirs("../assets", exist_ok=True)
    out_png  = "../assets/rip_field_fit.png"
    plt.savefig(out_png, dpi=300)
    print("Saved fit plot: ", out_png)

    # 4. save parameters for paper
    out_json = "../assets/rip_fit_params.json"
    with open(out_json,"w") as f: json.dump(dict(L=L, k=k, t0=t0, C=C), f, indent=2)
    print("Saved parameters: ", out_json)

if __name__ == "__main__":
    main()

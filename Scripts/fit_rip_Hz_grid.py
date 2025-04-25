# scripts/fit_rip_Hz_grid.py
import os, glob, itertools, numpy as np, pandas as pd, matplotlib.pyplot as plt
from astropy.cosmology import Planck18 as cosmo

# ------------------------------------------------------------------------
def time_to_z(time_myr):
    """map simulation look-back-time (Myr) → redshift using Planck18 age(z)"""
    t_gyr  = time_myr / 1_000.0
    z_grid = np.linspace(0.01, 10.0, 8000)
    ages   = np.array([cosmo.age(z).value for z in z_grid])        # Gyr
    return np.interp(t_gyr, ages[::-1], z_grid[::-1])

def load_rip_field():
    runs   = sorted(glob.glob("../data/run_*.csv"))
    rip    = np.mean([pd.read_csv(f)["rip_field"].values for f in runs], axis=0)
    t_myr  = pd.read_csv(runs[0])["time_myr"].values
    return rip, time_to_z(t_myr)

def obs_Hz():
    """chronometer compilation from your earlier script"""
    return pd.DataFrame({
        "z":[0.07,0.10,0.12,0.17,0.179,0.199,0.20,0.27,0.28,0.352,
             0.40,0.44,0.48,0.593,0.60,0.68,0.73,0.781,0.875,0.88,
             0.90,1.037,1.30,1.43,1.53,1.75,1.965,2.34,2.36],
        "H":[69.0,69.0,68.6,83.0,75.0,75.0,72.9,77.0,88.8,83.0,
             95.0,82.6,97.0,104.0,87.9,92.0,97.3,105.0,125.0,90.0,
             117.0,154.0,168.0,177.0,140.0,202.0,186.5,222.0,226.0],
        "err":[19.6,12.0,26.2,8.0,4.0,5.0,29.6,14.0,36.6,14.0,
               17.0,7.8,62.0,13.0,5.4,8.0,7.0,12.0,17.0,40.0,
               23.0,20.0,13.0,18.0,14.0,40.0,50.4,7.0,9.3]
    })

# ------------------------------------------------------------------------
rip_mean, z_sim          = load_rip_field()
H0, Om, Or               = cosmo.H0.value, cosmo.Om0, 9.24e-5
hz                       = obs_Hz()
z_obs, H_obs, H_err      = hz["z"].values, hz["H"].values, hz["err"].values

grid_w   = np.arange(0.50, 1.01, 0.05)          # 0.50 … 1.00
grid_omt = np.arange(0.64, 0.721, 0.01)         # 0.64 … 0.72

results  = []

for w, omt in itertools.product(grid_w, grid_omt):
    # scale the simulated rip so Ω_rip(z=0)=omt
    idx0          = np.argmin(z_sim)            # closest to today
    scale         = omt / rip_mean[idx0]
    omega_rip     = rip_mean * scale * (1 + z_sim) ** (-w)

    H_model_sim   = H0 * np.sqrt( Om*(1+z_sim)**3 + Or*(1+z_sim)**4 + omega_rip )
    # interpolate model to observed z-grid
    H_model_obs   = np.interp(z_obs, z_sim, H_model_sim)
    chi2          = np.sum(((H_model_obs - H_obs)/H_err)**2)
    results.append((w, omt, chi2))

# turn into DataFrame
df = pd.DataFrame(results, columns=["w","omega_rip_0","chi2"])
df.to_csv("../data/rip_gridsearch_chi2.csv", index = False)

# best fit
best = df.loc[df["chi2"].idxmin()]
print("\nBest fit:")
print(best)

# -------------- quick heat-map --------------
pivot = df.pivot(index="w", columns="omega_rip_0", values="chi2")
plt.figure(figsize=(7,5))
plt.imshow(pivot, origin="lower", aspect="auto",
           extent=[pivot.columns.min(), pivot.columns.max(),
                   pivot.index.min(),   pivot.index.max()],
           cmap="viridis_r")
plt.colorbar(label="χ²")
plt.scatter(best["omega_rip_0"], best["w"], color="red", marker="x")
plt.xlabel(r"$\Omega_{\mathrm{rip},0}$")
plt.ylabel(r"$w$  (evolution index)")
plt.title("χ² surface for rip-field H(z) fit")
os.makedirs("../data", exist_ok=True)
plt.savefig("../assets/rip_gridsearch_heatmap.png", dpi=300)
print("Saved heat-map & table to ../assets/")

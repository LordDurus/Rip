# fit_rip_Hz_grid.py
#
# 2-D grid-search in (Ω_rip_0 , w) against cosmic-chronometer H(z).
# Saves χ² surface, best–fit, and a heat-map with 1σ / 2σ contours.

import glob, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from astropy.cosmology import Planck18 as cosmo

# ----------------------------------------------------------------------
def load_simulation():
    files   = sorted(glob.glob("../data/run_*.csv"))
    rip_arr = np.array([pd.read_csv(f)["rip_field"].values for f in files])
    rip_avg = rip_arr.mean(axis=0)
    t_myr   = pd.read_csv(files[0])["time_myr"].values
    return t_myr, rip_avg

def time_to_z(time_myr):
    t_gyr   = time_myr / 1_000.0
    z_grid  = np.linspace(0.01, 10.0, 8000)
    ages    = np.array([cosmo.age(z).value for z in z_grid])           # Gyr
    return np.interp(t_gyr, ages[::-1], z_grid[::-1])

def model_Hz(z, omega_rip_0, w, rip_mean, z_sim):
    H0, Om, Or = cosmo.H0.value, cosmo.Om0, 9.24e-5
    # scale rip curve so value at z≈0 equals omega_rip_0
    idx0   = np.argmin(z_sim)
    scale  = omega_rip_0 / rip_mean[idx0]
    omega  = rip_mean * scale * (1 + z_sim)**(-w)
    # interpolate to requested z
    omega_z = np.interp(z, z_sim, omega)
    return H0 * np.sqrt(Om*(1+z)**3 + Or*(1+z)**4 + omega_z)

# ----------------------------------------------------------------------
# observed H(z)
hz_obs = pd.DataFrame({
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

# ----------------------------------------------------------------------
def main():
    t_myr, rip_mean = load_simulation()
    z_sim           = time_to_z(t_myr)

    omega_vals = np.arange(0.60, 0.7801, 0.005)
    w_vals     = np.arange(0.50, 1.0001, 0.05)
    chi2_grid  = np.zeros((w_vals.size, omega_vals.size))

    for i, w in enumerate(w_vals):
        for j, om_rip0 in enumerate(omega_vals):
            H_mod = model_Hz(hz_obs.z.values, om_rip0, w,
                             rip_mean, z_sim)
            chi2  = np.sum(((H_mod - hz_obs.H)/hz_obs.err)**2)
            chi2_grid[i, j] = chi2

    # ------------------------------------------------------------------
    # save results
    surface_df = pd.DataFrame(chi2_grid, index=w_vals, columns=omega_vals)
    surface_df.index.name  = "w"
    surface_df.columns.name = "Omega_rip_0"
    surface_df.to_csv("../data/rip_Hz_chi2_surface.csv")

    # locate minimum
    i_min, j_min = np.unravel_index(np.argmin(chi2_grid), chi2_grid.shape)
    best = pd.Series({
        "w":          w_vals[i_min],
        "omega_rip_0":omega_vals[j_min],
        "chi2":       chi2_grid[i_min, j_min]
    })
    best.to_frame().T.to_csv("../data/rip_Hz_bestfit.csv", index=False)

    # ------------------------------------------------------------------
    # plotting
    dchi2 = chi2_grid - best.chi2
    fig, ax = plt.subplots(figsize=(8,6))
    im = ax.imshow(chi2_grid, origin="lower",
                   extent=[omega_vals[0], omega_vals[-1],
                           w_vals[0], w_vals[-1]],
                   aspect="auto", cmap="viridis")
    cbar = fig.colorbar(im, ax=ax, label=r"$\chi^2$")

    # 1σ / 2σ contours
    cs1 = ax.contour(omega_vals, w_vals, dchi2,
                     levels=[2.30], colors="white", linestyles="--")
    cs2 = ax.contour(omega_vals, w_vals, dchi2,
                     levels=[6.17], colors="white", linestyles="-.")

    ax.clabel(cs1, fmt="1σ")
    ax.clabel(cs2, fmt="2σ")

    # mark best-fit
    ax.plot(best.omega_rip_0, best.w, "r*", ms=12)

    ax.set_xlabel(r"$\Omega_{\mathrm{rip},0}$")
    ax.set_ylabel(r"$w$ (evolution index)")
    ax.set_title(r"$\chi^2$ surface for rip-field $H(z)$ fit")

    os.makedirs("../assets", exist_ok=True)
    fig.savefig("../assets/rip_gridsearch_heatmap.png", dpi=300)
    print("Grid-search complete.")
    print("Best fit:\n", best)

# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()

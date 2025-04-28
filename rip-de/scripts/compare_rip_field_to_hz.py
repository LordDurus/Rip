import os, glob
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from astropy.cosmology import Planck18 as cosmo     # Planck-2018 parameters

# ---------- helpers ----------
def time_to_redshift(time_myr: np.ndarray) -> np.ndarray:
    """Map simulation look-back time (Myr) → redshift using Planck18 age(z)."""
    time_gyr = time_myr / 1_000.0
    z_grid  = np.linspace(0.01, 10.0, 8000)
    ages_gyr = np.array([cosmo.age(z).value for z in z_grid])
    return np.interp(time_gyr, ages_gyr[::-1], z_grid[::-1])       # oldest→newest

# ---------- main ----------
def main():

    # --- 1. load simulation ---
    run_files = sorted(glob.glob("../data/run_*.csv"))
    rip_runs  = [pd.read_csv(f)["rip_strength"].values for f in run_files]
    rip_mean  = np.mean(rip_runs, axis=0)
    time_myr  = pd.read_csv(run_files[0])["time_myr"].values
    z_sim     = time_to_redshift(time_myr)

    # --- 2. cosmological parameters (Planck18) ---
    H0        = cosmo.H0.value              # 67.7 km/s/Mpc
    omega_m   = cosmo.Om0                   # 0.315
    omega_r   = 9.24e-5                     # radiation density today

    # --- 3. map rip field → Ω_rip(z) so that Ω_rip(z=0)=1-Ω_m-Ω_r ---
    # omega_rip_today = 0.56              # pick the z=0 dark-energy share
    # omega_rip_today = 1.0 - omega_m - omega_r
    omega_rip_today = 0.72
    
    # print("omega_rip_today = ", omega_rip_today)
    
    idx_today = np.argmin(z_sim)  
    scale_factor = omega_rip_today / rip_mean[idx_today]
    omega_rip    = rip_mean * scale_factor
    w = 0.5
    omega_rip *= (1 + z_sim) ** (-w)    

    H_model = H0 * np.sqrt( omega_m * (1 + z_sim)**3 + omega_r * (1 + z_sim)**4 + omega_rip)

    # --- 5. observational H(z) data (cosmic chronometers sample) ---
    hz_data = pd.DataFrame({
        "z":  [0.07,0.10,0.12,0.17,0.179,0.199,0.20,0.27,0.28,0.352,
               0.40,0.44,0.48,0.593,0.60,0.68,0.73,0.781,0.875,0.88,
               0.90,1.037,1.30,1.43,1.53,1.75,1.965,2.34,2.36],
        "H":  [69.0,69.0,68.6,83.0,75.0,75.0,72.9,77.0,88.8,83.0,
               95.0,82.6,97.0,104.0,87.9,92.0,97.3,105.0,125.0,90.0,
               117.0,154.0,168.0,177.0,140.0,202.0,186.5,222.0,226.0],
        "err":[19.6,12.0,26.2,8.0, 4.0, 5.0,29.6,14.0,36.6,14.0,
               17.0, 7.8,62.0,13.0, 5.4, 8.0, 7.0,12.0, 17.0,40.0,
               23.0,20.0,13.0,18.0,14.0,40.0,50.4, 7.0, 9.3]
    })

    # --- 6. plot ---
    plt.figure(figsize=(12,7))

    order   = np.argsort(z_sim)
    z_plot  = z_sim[order]
    H_plot  = H_model[order]
    plt.plot(z_plot, H_plot, label="Total model $H(z)$ (matter+radiation+rip)", color="blue")
    #plt.plot(z_sim, H_model, label="Total model $H(z)$ (matter+radiation+rip)", color="blue")
    plt.errorbar(hz_data["z"], hz_data["H"], yerr=hz_data["err"], fmt="o", color="black", ecolor="gray", capsize=3, label="Observed cosmic-chronometer $H(z)$")
    plt.xlabel("Redshift  $z$")
    plt.ylabel("$H(z)$  [km s⁻¹ Mpc⁻¹]")
    plt.title("Rip-field cosmology compared with observational $H(z)$")
    plt.legend(); plt.grid(True); plt.tight_layout()    
    out = "../assets/rip_field_vs_hz.png"
    plt.savefig(out, dpi=300)
    print(f"Saved plot: {out}")

if __name__ == "__main__":
    main()

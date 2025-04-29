import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import glob
import os
import subprocess

# --- Load & stitch phases ---
infl = pd.read_csv('../rip-inf/data/simulation.csv')
infl['time'] = infl.index * 0.01

de_files = sorted(glob.glob('../rip-de/data/run_*.csv'))
if not de_files:
    raise FileNotFoundError("No run_*.csv found in rip-de/data/")
de = pd.read_csv(de_files[-1]).rename(columns={'time_myr':'time'})
de['time'] += infl['time'].iloc[-1] + 0.1

# Full arrays
T_full = np.concatenate([infl.time.values, de.time.values])
A_full = np.concatenate([infl.scale_factor.values, de.scale_factor.values])

# Split indices
N_infl  = len(infl)
N_total = len(T_full)

# Decide how many frames we want, and split them
N_frames      = 500
infl_frac     = 0.2
N_inf_frames  = int(N_frames * infl_frac)
N_de_frames   = N_frames - N_inf_frames

# Pre-slice for convenience
infl_x, infl_y = T_full[:N_infl], A_full[:N_infl]
dark_x, dark_y = T_full[N_infl:], A_full[N_infl:]

# --- Helpers ---
def blend_color(norm):
    # blue → red
    return (norm, 0.0, 1.0 - norm)

def phase_label(time_val):
    end_infl = infl_x[-1]
    if time_val < end_infl:
        return "Inflation Phase"
    elif time_val < end_infl + 5000:
        return "Matter Domination"
    else:
        return "Dark Energy Domination"

# --- Figure setup ---
fig, ax = plt.subplots(figsize=(10, 6))
ax.set_yscale('log')
ax.set_xlim(T_full.min(), T_full.max())
ax.set_ylim(1, A_full.max() * 1.2)
ax.grid(True, which='both', linestyle='--', alpha=0.3)
ax.set_xlabel("Time (Myr or sim units)")
ax.set_ylabel("Scale Factor (log)")
ax.set_title("Combined Scale Factor Evolution")

line, = ax.plot([], [], lw=4)
txt = ax.text(
    0.05, 0.95, "",
    transform=ax.transAxes,
    fontsize=14, va='top',
    bbox=dict(facecolor='white', alpha=0.8, boxstyle='round')
)

# --- Init / Animate ---
def init():
    line.set_data([], [])
    txt.set_text("Starting simulation…")
    txt.set_alpha(1.0)
    return line, txt

def animate(frame):
    if frame < N_inf_frames:
        # Inflation sweep
        idx = int(frame / (N_inf_frames - 1) * (N_infl - 1))
        x = infl_x[:idx + 1]
        y = infl_y[:idx + 1]
        line.set_data(x, y)
        line.set_color((0.5, 0.5, 0.5))
        txt.set_text("Inflation Phase")
        txt.set_alpha(1.0)

    else:
        # Dark-energy sweep
        j = frame - N_inf_frames
        idx_de = int(j / (N_de_frames - 1) * (len(dark_x) - 1))
        x = np.concatenate([infl_x[-1:], dark_x[:idx_de + 1]])
        y = np.concatenate([infl_y[-1:], dark_y[:idx_de + 1]])

        norm = j / (N_de_frames - 1)
        line.set_data(x, y)
        line.set_color(blend_color(norm))

        # Zoom in on dark-energy scale once
        if frame == N_inf_frames:
            ax.set_ylim(dark_y.min() * 0.9, dark_y.max() * 1.1)

        txt.set_text(phase_label(x[-1]))
        txt.set_alpha(1.0)

    return line, txt

# --- Build & save ---
ani = animation.FuncAnimation(
    fig, animate,
    frames=N_frames,
    init_func=init,
    interval=30,
    blit=False
)

os.makedirs('../assets', exist_ok=True)
gif_path = '../assets/combined_scale_factor_animation.gif'
ani.save(gif_path, writer='pillow', fps=20)
print("Saved animation to", gif_path)

# Optionally compress with gifsicle
try:
    subprocess.run(
        ["gifsicle", "-O3", "--colors", "256", gif_path, "-o", gif_path],
        check=True
    )
    print("Compressed with gifsicle")
except FileNotFoundError:
    pass

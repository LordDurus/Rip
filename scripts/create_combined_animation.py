import sys
#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import glob, os, subprocess

# ———————————————
# CONFIGURATION
# ———————————————
N_FRAMES    = 400
INFL_FRAC   = 0.15   # ← increased from 0.05 to slow inflation spike

INF_PATH    = os.path.join('..','rip-inf','data','simulation.csv')
DE_GLOB     = os.path.join('..','rip-de','data','run_*.csv')
OUT_GIF     = os.path.join('..','assets','combined_scale_factor_animation.gif')
# ———————————————

# ———————————————
# 1) Load + stitch phases
# ———————————————
infl = pd.read_csv(INF_PATH)
infl['time'] = infl.index * 0.01

de_files = sorted(glob.glob(DE_GLOB))
if not de_files:
    raise RuntimeError(f"No dark-energy files matching {DE_GLOB}")
de = pd.read_csv(de_files[-1]).rename(columns={'time_myr':'time'})
de['time'] += infl['time'].iloc[-1] + 0.1

T_inf, A_inf = infl['time'].values, infl['scale_factor'].values
T_de , A_de  = de['time'].values,   de['scale_factor'].values

n_inf_frames = max(5, int(N_FRAMES * INFL_FRAC))
n_de_frames  = N_FRAMES - n_inf_frames

idx_inf = np.linspace(0, len(T_inf)-1, n_inf_frames, dtype=int)
idx_de  = np.linspace(0, len(T_de )-1, n_de_frames,  dtype=int)

# ———————————————
# 2) Helpers
# ———————————————
def blend_color(fraction):
    return (fraction, 0.0, 1.0 - fraction)

def phase_label(t):
    if t <= T_inf[-1]:
        return "Inflation Phase"
    elif t <= T_inf[-1] + 5000:
        return "Matter Domination"
    else:
        return "Dark Energy Domination"

# ———————————————
# 3) Figure setup
# ———————————————
fig, ax = plt.subplots(figsize=(10,6))
ax.set_yscale('log')
ax.set_xlim(min(T_inf.min(), T_de.min()), max(T_inf.max(), T_de.max()))
ax.set_ylim(min(A_inf.min(), A_de.min())*0.9, max(A_inf.max(), A_de.max())*1.2)
ax.grid(True, which='both', linestyle='--', alpha=0.25)
ax.set_xlabel("Time (Myr or sim units)")
ax.set_ylabel("Scale Factor")
ax.set_title("Combined Scale Factor Evolution")

line, = ax.plot([], [], lw=3)
txt  = ax.text(0.05, 0.95, "", transform=ax.transAxes,
               fontsize=14, va='top',
               bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

# ———————————————
# 4) Animation callbacks
# ———————————————
def init():
    line.set_data([], [])
    txt.set_text("Starting…")
    txt.set_alpha(1.0)
    return line, txt

def animate(frame):
    if frame < n_inf_frames:
        i = idx_inf[frame]
        x, y = T_inf[:i+1], A_inf[:i+1]
        line.set_data(x, y)
        line.set_color('gray')
        txt.set_text("Inflation Phase")
        txt.set_alpha(1.0)
    else:
        j = frame - n_inf_frames
        k = idx_de[j]
        x = np.concatenate([T_inf[-1:], T_de[:k+1]])
        y = np.concatenate([A_inf[-1:], A_de[:k+1]])
        if frame == n_inf_frames:
            ax.set_yscale('linear')
            ax.set_ylim(A_de.min()*0.9, A_de.max()*1.1)
        frac = j / (n_de_frames-1)
        line.set_data(x, y)
        line.set_color(blend_color(frac))
        txt.set_text(phase_label(x[-1]))
        txt.set_alpha(1.0)
    return line, txt

# ———————————————
# 5) Build & save
# ———————————————
ani = animation.FuncAnimation(
    fig, animate,
    frames=N_FRAMES,
    init_func=init,
    interval=30,
    blit=False
)


ani.save(OUT_GIF, writer='pillow', fps=20)
print("Saved:", OUT_GIF)

try:
    subprocess.run(
        ["gifsicle","-O3","--colors","256", OUT_GIF, "-o", OUT_GIF],
        check=True
    )
    print("Compressed with gifsicle")
except FileNotFoundError:
    pass

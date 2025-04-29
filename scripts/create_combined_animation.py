# scripts/create_combined_animation.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import glob, os, subprocess

# --- load & stitch phases ---
infl = pd.read_csv('../rip-inf/data/simulation.csv')
infl['time'] = infl.index * 0.01
de_files = sorted(glob.glob('../rip-de/data/run_*.csv'))
de = pd.read_csv(de_files[-1]).rename(columns={'time_myr':'time'})
de['time'] += infl['time'].iloc[-1] + 0.1

# combine arrays
T_full = np.concatenate([infl.time.values, de.time.values])
A_full = np.concatenate([infl.scale_factor.values, de.scale_factor.values])

# split indices
N_infl = len(infl)
N_total = len(T_full)
N_dark = len(de)

# dark‐energy min/max
A_dark = A_full[N_infl:]
min_dark, max_dark = A_dark.min(), A_dark.max()

# --- helpers ---
def blend_color(norm):
    # blue→red
    return ( norm, 0.0, 1.0 - norm )

def phase_label(t):
    if t < infl['time'].iloc[-1]:
        return "Inflation Phase"
    elif t < infl['time'].iloc[-1] + 5000:
        return "Matter Domination"
    else:
        return "Dark Energy Domination"

# --- figure setup ---
fig, ax = plt.subplots(figsize=(10,6))
ax.set_yscale('log')
ax.set_xlim(T_full.min(), T_full.max())
ax.set_ylim(1, A_full.max()*1.2)
ax.grid(True, which='both', linestyle='--', alpha=0.3)
ax.set_xlabel("Time (Myr or sim units)")
ax.set_ylabel("Scale Factor (log)")
ax.set_title("Combined Scale Factor Evolution")

line, = ax.plot([], [], lw=4)
txt = ax.text(0.05, 0.95, "", transform=ax.transAxes,
              fontsize=14, va='top',
              bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

# split out the two segments once
infl_x, infl_y = T_full[:N_infl], A_full[:N_infl]
dark_x, dark_y = T_full[N_infl:], A_full[N_infl:]

# one-time zoom flag
first_zoom = {"done": False}

# --- init & animate ---
def init():
    line.set_data([], [])
    txt.set_text("Starting simulation…")
    txt.set_alpha(1.0)
    return line, txt

def animate(i):
    # Phase 1: Inflation spike
    if i < N_infl:
        x = infl_x[: i+1]
        y = infl_y[: i+1]
        line.set_data(x, y)
        line.set_color((0.5,0.5,0.5))    # gray
        line.set_linewidth(4)
        txt.set_text("Inflation Phase")
        txt.set_alpha(1.0)

    # Phase 2: Dark-energy growth
    else:
        # zoom Y-axis once
        if not first_zoom["done"]:
            ax.set_ylim(dark_y.min()*0.9, dark_y.max()*1.1)
            first_zoom["done"] = True

        # redraw entire inflation in the background
        ax.lines[0].set_data(infl_x, infl_y)
        ax.lines[0].set_color((0.8,0.8,0.8))
        ax.lines[0].set_linewidth(1)

        # now draw the dark segment up to frame j
        j = i - N_infl
        norm = j / (len(dark_x)-1)
        x = dark_x[: j+1]
        y = dark_y[: j+1]
        line.set_data(x, y)
        line.set_color((norm, 0.0, 1.0-norm))  # blue→red
        line.set_linewidth(4)

        txt.set_text(
            "Dark Energy Domination" 
            if dark_x[j] >= infl_x[-1] + 5000 
            else "Matter Domination"
        )
        txt.set_alpha(1.0)

    return line, txt


animate.first_dark = True

# --- build & save ---
ani = animation.FuncAnimation(
    fig, animate,
    init_func=init,
    frames=N_total,
    interval=30,
    blit=False
)

out = '../assets/combined_scale_factor_animation.gif'
ani.save(out, writer='pillow', fps=20)
print("Saved to", out)

# optional compression
try:
    subprocess.run(
        ["gifsicle","-O3","--colors","256",out,"-o",out],
        check=True
    )
    print("Compressed!")
except FileNotFoundError:
    pass

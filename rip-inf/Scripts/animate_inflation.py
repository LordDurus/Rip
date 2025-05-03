import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
import subprocess

if not os.path.exists('../data/simulation.csv') and os.path.exists('../data/simulation.csv.gz'):
    import gzip
    with gzip.open('../data/simulation.csv.gz', 'rb') as f_in:
        with open('../data/simulation.csv', 'wb') as f_out:
            f_out.write(f_in.read())            

# load the csv
df = pd.read_csv('../data/simulation.csv', dtype={
    'time': float,
    'rip_strength': float,
    'scale_factor': float,
    'x': float,
    'y': float,
    'z': float,
    'vx': float,
    'vy': float,
    'vz': float
})

# fix rounding
df['time'] = df['time'].round(6)

# remove near-zero or bad values
epsilon = 1e-6
df = df[(df['time'] > epsilon) & (df['scale_factor'] > epsilon)]
time_only_df = df.drop_duplicates(subset='time').reset_index(drop=True)

# create figure
fig, ax = plt.subplots(figsize=(10, 6))
ax.set_xlabel('Time (log scale)')
ax.set_ylabel('Scale Factor (Universe Size, log scale)')
ax.set_xscale('log')
ax.set_yscale('log')
ax.grid(True, which="both", ls="--")
line, = ax.plot([], [], lw=2, label='Scale Factor')
ax.legend()

# set axis limits once
ax.set_xlim(df['time'].min(), df['time'].max())
ax.set_ylim(df['scale_factor'].min(), df['scale_factor'].max())

# animation update function
def update(frame):
    current_time = time_only_df.iloc[frame]['time']
    current_df = df[df['time'] <= current_time]
    line.set_data(current_df['time'], current_df['scale_factor'])
    return line,

# create animation
ani = animation.FuncAnimation(fig, update, frames=len(time_only_df), interval=20, blit=True)

# save animation
gif_path = '../assets/inflation_animation.gif'
ani.save(gif_path, writer='pillow', fps=30)
print("Animation saved to assets/inflation_animation.gif")

# ---------- Shrink with gifsicle if available ----------
try:
    subprocess.run(["gifsicle", "-O3", "--colors", "256", "-i", gif_path, "-o", gif_path], check=True)    
except FileNotFoundError:
    print("gifsicle not found. Skipping compression. Install gifsicle to optimize GIF size.")

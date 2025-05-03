import pandas as pd
import matplotlib.pyplot as plt
import os
import shutil
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
df = df[(df['time'] > epsilon) & (df['scale_factor'] > epsilon) & (df['rip_strength'] > epsilon)]

# find inflation end
rip_threshold = 1.0
inflation_end = df[df['rip_strength'] < rip_threshold].iloc[0]['time']

# plot
fig, ax1 = plt.subplots(figsize=(10, 6))

color = 'tab:blue'
ax1.set_xlabel('Time (log scale)')
ax1.set_ylabel('Scale Factor (Universe Size)', color=color)
ax1.plot(df['time'], df['scale_factor'], color=color, label='Scale Factor', linewidth=2)
ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.tick_params(axis='y', labelcolor=color)

# create second y-axis
ax2 = ax1.twinx()

color = 'tab:red'
ax2.set_ylabel('Rip Field Strength', color=color)
ax2.plot(df['time'], df['rip_strength'], color=color, linestyle='--', label='Rip Strength', linewidth=2)
ax2.set_yscale('log')
ax2.tick_params(axis='y', labelcolor=color)

# draw vertical line at inflation end
ax1.axvline(x=inflation_end, color='green', linestyle=':', linewidth=2, label='Inflation Ends')
ax1.legend(loc='lower right')

plt.title('Rip Field Inflation Simulation')
fig.tight_layout()

# save the figure

output_file = "../assets/scale_factor_rip_plot_inflation_end.png"
plt.savefig(output_file, dpi=300)

if shutil.which('optipng.exe'):
	try:
		subprocess.run(['optipng.exe', '-o7', output_file], check=True)            
	except subprocess.CalledProcessError as e:
		print(f"optipng failed: {e}")
else:
	print("optipng not found in PATH; skipping PNG optimization.")

print(f"Saved plot: {output_file}")

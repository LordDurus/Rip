import pandas as pd
import matplotlib.pyplot as plt
import os

# load the csv
df = pd.read_csv('../data/simulation.csv')

# fix rounding
df['time'] = df['time'].round(6)

# remove near-zero or bad values
epsilon = 1e-6
df = df[(df['time'] > epsilon) & (df['scale_factor'] > epsilon) & (df['rip_strength'] > epsilon)]

# find inflation end
rip_threshold = 1.0
inflation_end = df[df['rip_strength'] < rip_threshold].iloc[0]['time']

# make sure assets folder exists
os.makedirs('assets', exist_ok=True)

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
plt.savefig('../assets/scale_factor_rip_plot_inflation_end.png', dpi=300)
print("Plot saved to assets/scale_factor_rip_plot_inflation_end.png")

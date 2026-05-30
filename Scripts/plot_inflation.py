import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import shutil
import subprocess

# connect to the database
db_path = '../../data/rip_data.db'
if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)

# query the data (assumes one row per timestep for plotting)
query = """
select timestep, rip_strength, scale_factor
from cell
group by timestep
order by timestep
"""

df = pd.read_sql_query(query, conn)
conn.close()

# convert timestep to time (assuming you know step_duration from config)
step_duration = 0.05  # adjust if needed
df['time'] = df['timestep'] * step_duration

# clean and filter
epsilon = 1e-6
df = df[(df['time'] > epsilon) & (df['scale_factor'] > epsilon) & (df['rip_strength'] > epsilon)]

# find inflation end
rip_threshold = 1.0
subset = df[df['rip_strength'] < rip_threshold]

if subset.empty:
    print("Warning: No rows found below rip_threshold. Using max timestep.")
    inflation_end = df['timestep'].max()
else:
    inflation_end = subset.iloc[0]['time']

# plot
fig, ax1 = plt.subplots(figsize=(10, 6))

# primary axis (scale factor)
ax1.set_xlim(left=1e-2, right=1e2) 
ax1.set_xlabel('Time (log scale)')
ax1.set_ylabel('Scale Factor (Universe Size)', color='tab:blue')
line1, = ax1.plot(df['time'], df['scale_factor'], color='tab:blue', label='Scale Factor', linewidth=2)
ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.tick_params(axis='y', labelcolor='tab:blue')

# secondary axis (rip strength)
ax2 = ax1.twinx()
ax2.set_ylabel('Rip  Strength', color='tab:red')
line2, = ax2.plot(df['time'], df['rip_strength'], color='tab:red', linestyle='--', label='Rip Strength', linewidth=2)
ax2.set_yscale('log')
ax2.tick_params(axis='y', labelcolor='tab:red')

# inflation end marker
line3 = ax1.axvline(x=inflation_end, color='green', linestyle=':', linewidth=2, label='Inflation Ends')

# combine all for legend
lines = [line1, line2, line3]
labels = [line.get_label() for line in lines]
ax1.legend(lines, labels, loc='center left', framealpha=0.9, facecolor='white')

plt.title('Rip Inflation Simulation')
fig.tight_layout()
# plot end


# save
output_file = "../output/plot_inflation.png"
plt.savefig(output_file, dpi=300)

# optional PNG optimization
if shutil.which('optipng.exe'):
	try:
		subprocess.run(['optipng.exe', '-o7', output_file], check=True)
	except subprocess.CalledProcessError as e:
		print(f"optipng failed: {e}")
else:
	print("optipng not found in PATH; skipping PNG optimization.")

print(f"Saved plot: {output_file}")

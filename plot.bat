del /q output\*.png
cls
cd scripts
plot_inflation.py --run-id 1
py plot_cmb_power.py
py plot_cmb_power.py --field matter_density
plot_cmb_power.py --field curvature --timestep 119
plot_cmb_power.py --field rip_strength
cd..
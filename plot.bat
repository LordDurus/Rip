del /q output\*.png
del /q output\*.html
cls
cd scripts
set run_id=1
set timestep=2000
plot_inflation.py --run-id 1
py plot_cmb_power.py --run-id %run_id% --timestep %timestep%
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field matter_density
plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field curvature
plot_cmb_power.py --run-id %run_id% --timestep %timestep%  --field rip_strength
plot_structure.py --run-id %run_id% --timestep %timestep%
plot_3d.py --run-id %run_id% --timestep %timestep% --density-percentile 95
cd..

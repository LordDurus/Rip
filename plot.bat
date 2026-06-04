@echo off
setlocal

:: Optional parameters — override via command line:
:: plot.bat [run_id] [timestep]
:: Example: plot.bat 2 500

:: Defaults
set run_id=1
set timestep=2000

:: Override if arguments provided
if not "%~1"=="" set run_id=%~1
if not "%~2"=="" set timestep=%~2

echo Running plots for run_id=%run_id%, timestep=%timestep%

del /q output\*.png 2>nul
del /q output\*.html 2>nul
cls

cd scripts

py plot_inflation.py --run-id %run_id%
py plot_cmb_power.py --run-id %run_id% --timestep %timestep%
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field matter_density
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field curvature
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field rip_strength
py plot_structure.py --run-id %run_id% --timestep %timestep%
py plot_3d.py --run-id %run_id% --timestep %timestep% --density-percentile 95

cd ..

echo Done.
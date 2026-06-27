@echo off
setlocal

:: Optional parameters — override via command line:
:: plot.bat [run_id] [timestep]
:: Example: plot.bat 2 500

:: Defaults
set run_id=1
set timestep=3000

:: Override if arguments provided
if not "%~1"=="" set run_id=%~1
if not "%~2"=="" set timestep=%~2

echo Running plots for run_id=%run_id%, timestep=%timestep%

del /q output\*.png 2>nul
del /q output\*.html 2>nul
del /q output\*.txt 2>nul

cd scripts
set output_folder=../output
set validation_file=%output_folder%/validation_run%run_id%.txt
py export_log.py --run-id %run_id%
py generate_flowchart.py
py plot_inflation.py --run-id %run_id%
py plot_cmb_power.py --run-id %run_id% --timestep %timestep%
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field matter_density
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field curvature
py plot_cmb_power.py --run-id %run_id% --timestep %timestep% --field rip_strength
py plot_cmb.py --run-id %run_id%
py plot_lensing.py --run-id %run_id%
py plot_structure.py --run-id %run_id% --timestep %timestep%
py plot_3d.py --run-id %run_id% --timestep %timestep% --density-percentile 95
py plot_matter.py --run-id %run_id%
py plot_smbh.py --run-id %run_id% --timestep %timestep%
py plot_galaxy.py --run-id %run_id% --timestep %timestep%
py plot_offset_trajectory.py --run-id %run_id% >> %validation_file%
py plot_stability.py --run-id %run_id% >> %validation_file%
py dump_run_settings.py --run-id %run_id% >> %validation_file%
py bullet_offset_firstpass.py --run-id %run_id% --coarse-stride 5 --max-timestep %timestep% --window 4 --no-trajectory >> %validation_file%

rem Debug
py bullet_offset_diagnostic.py --run-id %run_id% --timestep 1 >> %validation_file%
py bullet_offset_diagnostic.py --run-id %run_id% --timestep 50 >> %validation_file%
py bullet_offset_diagnostic.py --run-id %run_id% --timestep 150 >> %validation_file%
py bullet_offset_diagnostic.py --run-id %run_id% --timestep 199 >> %validation_file%


if %timestep% GTR 249 (
	py bullet_offset_diagnostic.py --run-id %run_id% --timestep 250 >> %validation_file%
	if %timestep% GTR 1499 (
		py bullet_offset_diagnostic.py --run-id %run_id% --timestep 1500 >> %validation_file%
	}
	if %timestep% GTR 2999 (
		py bullet_offset_diagnostic.py --run-id %run_id% --timestep 3000 >> %validation_file%
	}
	if %timestep% GTR 4998 (
		py bullet_offset_diagnostic.py --run-id %run_id% --timestep 4999 >> %validation_file%
	}
)

rem Run this last to get all the PNG files created.
py combine_plots.py --run-id %run_id% --folder %output_folder%

cd ..
echo Done.

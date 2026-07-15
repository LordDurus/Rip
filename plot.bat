@echo off
setlocal

:: Optional parameters -- override via command line:
:: plot.bat [run_id] [timestep]
:: Example: plot.bat 2 500

:: Defaults
set run_id=1
set timestep=9999

:: Override if arguments provided
if not "%~1"=="" set run_id=%~1
if not "%~2"=="" set timestep=%~2

echo Running plots for run_id=%run_id%, timestep=%timestep%

:: delete run specific files 
del /q output\*_run%run_id%*.* > nul

set output_folder=../../output
set validation_file=%output_folder%/validation_run%run_id%.txt

:: Start running scripts
cd scripts\diagnostics
py export_log.py --run-id %run_id%
py dump_run_settings.py --run-id %run_id% >> %validation_file%
py dimple_infall.py --run-id %run_id% >> %validation_file%
cd ..\generate
py flowchart.py
cd ..\plots
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
cd ..\bullets
py offset_firstpass.py --run-id %run_id% --coarse-stride 5 --max-timestep %timestep% --window 3 --no-trajectory >> %validation_file%
py offset_firstpass.py --run-id %run_id% --coarse-stride 5 --max-timestep %timestep% --post-pass --no-trajectory >> %validation_file%
py offset_diagnostic.py --run-id %run_id% --max-timestep 1 >> %validation_file%
if %timestep% GTR 49 py offset_diagnostic.py --run-id %run_id% --max-timestep 50 >> %validation_file%
if %timestep% GTR 149 py offset_diagnostic.py --run-id %run_id% --max-timestep 150 >> %validation_file%
if %timestep% GTR 199 py offset_diagnostic.py --run-id %run_id% --max-timestep 199 >> %validation_file%
if %timestep% GTR 249 py offset_diagnostic.py --run-id %run_id% --max-timestep 250 >> %validation_file%
if %timestep% GTR 1499 py offset_diagnostic.py --run-id %run_id% --max-timestep 1500 >> %validation_file%
if %timestep% GTR 1499 py offset_firstpass.py --run-id %run_id% --coarse-stride 5 --max-timestep 1500 --post-pass >> %validation_file%
if %timestep% GTR 2999 py offset_diagnostic.py --run-id %run_id% --max-timestep 3000 >> %validation_file%
if %timestep% GTR 4998 py offset_diagnostic.py --run-id %run_id% --max-timestep 4999 >> %validation_file%
if %timestep% GTR 6998 py offset_diagnostic.py --run-id %run_id% --max-timestep 6999 >> %validation_file%
if %timestep% GTR 7998 py offset_diagnostic.py --run-id %run_id% --max-timestep 7999 >> %validation_file%
if %timestep% GTR 8998 py offset_diagnostic.py --run-id %run_id% --max-timestep 8999 >> %validation_file%
if %timestep% GTR 9998 py offset_diagnostic.py --run-id %run_id% --max-timestep 9999 >> %validation_file%

:: Run this last to get all the PNG files created.
cd ..\diagnostics
py combine_plots.py --run-id %run_id% --folder %output_folder%

:: Post-run regression checks: PASS/FAIL/WEIRD per validated mechanism,
:: graded into the validation file so a template slip or physics regression
:: is one grep away instead of a plot read.
py post_run_checks.py --run-id %run_id% >> %validation_file%

:: Append the run log to the validation file -- one upload instead of two.
:: Done here (still inside scripts\diagnostics) so the relative paths in
:: %validation_file% and the type argument both resolve; after cd ..\.. they would not.
echo: >> %validation_file%
echo ===== RUN LOG (log_run%run_id%.csv) ===== >> %validation_file%
type "..\..\output\log_run%run_id%.csv" >> %validation_file%

cd ..\..
echo Done.
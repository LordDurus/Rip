@echo off
cls
cargo run --release
if %ERRORLEVEL% neq 0 (
    echo.
    echo Cargo run failed with error %ERRORLEVEL% -- skipping plots.
    exit /b %ERRORLEVEL%
)
rem plot.bat
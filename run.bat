:: To generate code/markdown
:: Being in Scripts/generate run
:: py code.py
:: py db_to_markdown.py 

@echo off
cls

cargo run --release
set RC=%ERRORLEVEL%

echo Cargo returned %RC%

if %RC% neq 0 (
    echo.
    echo Cargo run failed with error %RC% -- skipping plots.
    exit /b %RC%
)

plot.bat
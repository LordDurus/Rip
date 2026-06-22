
# py generate_entities.py ../data/template.db --out-dir ../src/database/entities --mod-rs --with-new --derive-for cell_position=Debug,Clone,PartialEq,Eq,Hash
@echo off
cls
cargo run --release
if %ERRORLEVEL% neq 0 (
    echo.
    echo Cargo run failed with error %ERRORLEVEL% -- skipping plots.
    exit /b %ERRORLEVEL%
)
plot.bat
@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_demo.py
) else (
    python run_demo.py
)
if errorlevel 1 (
    echo.
    echo Cannot start demo. See README.md for setup instructions.
    pause
)

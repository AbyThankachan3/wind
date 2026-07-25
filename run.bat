@echo off
REM ============================================================
REM  Wind pipeline launcher (Windows)
REM  Double-click this file to run the whole pipeline.
REM  It sets up everything automatically on first run.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === Wind pipeline ===
echo.

REM ---- 1. Check Python is installed ----
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo During install, tick "Add Python to PATH", then run this file again.
    echo.
    pause
    exit /b 1
)

REM ---- 2. Create a local virtual environment on first run ----
if not exist ".venv\Scripts\python.exe" (
    echo Creating a local Python environment ^(.venv^)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

set "PY=.venv\Scripts\python.exe"

REM ---- 3. Install / update dependencies ----
echo Installing dependencies ^(first run can take several minutes^)...
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Some dependencies failed to install. See the messages above.
    pause
    exit /b 1
)

REM ---- 4. Run the pipeline ----
echo.
"%PY%" run_all.py

echo.
pause

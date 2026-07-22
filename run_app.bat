@echo off
setlocal
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [HINT] Run create_venv.bat first.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Verification rapide et non bloquante d'une nouvelle version (timeout court, ignoree si hors ligne).
python scripts\update_project.py --check-only

echo [INFO] Launching Streamlit app...
streamlit run app.py

if errorlevel 1 (
    echo [ERROR] Streamlit execution failed.
    pause
    exit /b 1
)

endlocal

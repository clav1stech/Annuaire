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

echo [INFO] Launching Name Search app on port 8502...
streamlit run name_search_app.py --server.port 8502

if errorlevel 1 (
    echo [ERROR] Streamlit execution failed.
    pause
    exit /b 1
)

endlocal

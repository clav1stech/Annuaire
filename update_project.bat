@echo off
setlocal
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=py"
            set "PYTHON_ARGS=-3"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] No Python interpreter found.
    echo [HINT] Install Python 3.11-3.14 first ^(see README^).
    pause
    exit /b 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% scripts\update_project.py %*

pause
endlocal

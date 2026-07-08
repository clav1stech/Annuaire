@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

echo [INFO] Working directory: %CD%
echo [INFO] Creating virtual environment if needed...

if not exist "%VENV_DIR%\Scripts\python.exe" (
    if exist "C:\Users\Public\Anaconda3\python.exe" (
        if exist "C:\Users\Public\Anaconda3\envs\lexifact\python.exe" (
            set "SELECTED_PYTHON=C:\Users\Public\Anaconda3\envs\lexifact\python.exe"
        ) else if exist "C:\Users\Public\Anaconda3\envs\tokenizer\python.exe" (
            set "SELECTED_PYTHON=C:\Users\Public\Anaconda3\envs\tokenizer\python.exe"
        ) else (
            set "SELECTED_PYTHON=C:\Users\Public\Anaconda3\python.exe"
        )

        echo [INFO] Using Python interpreter: !SELECTED_PYTHON!
        "!SELECTED_PYTHON!" -m venv "%VENV_DIR%"
        if errorlevel 1 (
            echo [WARN] Standard venv failed, trying virtualenv fallback...
            "C:\Users\Public\Anaconda3\python.exe" -m pip install --user virtualenv
            if errorlevel 1 (
                echo [ERROR] Failed to install virtualenv fallback.
                pause
                exit /b 1
            )
            "C:\Users\Public\Anaconda3\python.exe" -m virtualenv -p "!SELECTED_PYTHON!" "%VENV_DIR%"
        )
    ) else (
        where py >nul 2>&1
        if errorlevel 1 (
            where python >nul 2>&1
            if errorlevel 1 (
                echo [ERROR] No Python interpreter found.
                echo [HINT] Install Python 3.11/3.12 or update create_venv.bat path.
                pause
                exit /b 1
            ) else (
                python -m venv "%VENV_DIR%"
            )
        ) else (
            py -3 -m venv "%VENV_DIR%"
        )
    )
    if not exist "%VENV_DIR%\Scripts\python.exe" (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment is incomplete: activate.bat not found.
    pause
    exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [INFO] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [SUCCESS] Environment is ready.
endlocal

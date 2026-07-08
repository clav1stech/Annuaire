@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

echo [INFO] Working directory: %CD%

echo [INFO] Detecting installed Python version...
set "PY_VERSION="
where python >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%V in ('python --version 2^>^&1') do set "PY_VERSION=%%V"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=2" %%V in ('py -3 --version 2^>^&1') do set "PY_VERSION=%%V"
    )
)

if defined PY_VERSION (
    echo [INFO] Detected Python version: !PY_VERSION!
    set "PY_MAJOR="
    set "PY_MINOR="
    for /f "tokens=1,2 delims=." %%A in ("!PY_VERSION!") do (
        set "PY_MAJOR=%%A"
        set "PY_MINOR=%%B"
    )
    set "PY_IN_RANGE=0"
    if "!PY_MAJOR!"=="3" if !PY_MINOR! GEQ 11 if !PY_MINOR! LEQ 12 set "PY_IN_RANGE=1"
    if "!PY_IN_RANGE!"=="0" (
        echo [WARN] Python !PY_VERSION! est hors de la plage officiellement testee de ce projet ^(3.11-3.12^).
        echo [WARN] L'installation peut fonctionner grace aux wheels precompilees de pyarrow/duckdb, mais n'est pas garantie.
        choice /C ON /N /M "Continuer avec Python !PY_VERSION! (O) ou annuler (N) ? "
        if errorlevel 2 (
            echo [INFO] Installation annulee par l'utilisateur.
            exit /b 0
        )
    )
) else (
    echo [WARN] Impossible de detecter automatiquement la version de Python installee.
)

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
echo [INFO] pyarrow and duckdb are restricted to precompiled wheels ^(no source build^)...
pip install --only-binary=pyarrow --only-binary=duckdb -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    echo [HINT] If the error mentions pyarrow or duckdb, no precompiled wheel is available
    echo [HINT] for this Python version. Use Python 3.11 or 3.12, or check pypi.org for
    echo [HINT] wheel availability before retrying.
    pause
    exit /b 1
)

echo [SUCCESS] Environment is ready.
endlocal

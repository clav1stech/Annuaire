@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

echo [INFO] Working directory: %CD%

echo [INFO] Detecting installed Python version...
set "PYTHON_EXE="
set "PYTHON_ARGS="

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo [INFO] Python introuvable sur le PATH, recherche dans les emplacements Anaconda/Miniconda courants...
    for %%D in (
        "%USERPROFILE%\Anaconda3"
        "%USERPROFILE%\anaconda3"
        "%USERPROFILE%\Miniconda3"
        "%USERPROFILE%\miniconda3"
        "C:\ProgramData\Anaconda3"
        "C:\ProgramData\Miniconda3"
        "C:\Users\Public\Anaconda3"
        "C:\Users\Public\Miniconda3"
    ) do (
        if not defined PYTHON_EXE if exist "%%~D\python.exe" (
            set "PYTHON_EXE=%%~D\python.exe"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] No Python interpreter found.
    echo [HINT] Install Python 3.11-3.14, or make sure your existing installation
    echo [HINT] ^(Anaconda/Miniconda included^) has its python.exe reachable from the PATH.
    pause
    exit /b 1
)

for /f "tokens=2" %%V in ('"!PYTHON_EXE!" !PYTHON_ARGS! --version 2^>^&1') do set "PY_VERSION=%%V"

if defined PY_VERSION (
    echo [INFO] Detected Python version: !PY_VERSION! ^(!PYTHON_EXE! !PYTHON_ARGS!^)
    set "PY_MAJOR="
    set "PY_MINOR="
    for /f "tokens=1,2 delims=." %%A in ("!PY_VERSION!") do (
        set "PY_MAJOR=%%A"
        set "PY_MINOR=%%B"
    )
    set "PY_IN_RANGE=0"
    if "!PY_MAJOR!"=="3" if !PY_MINOR! GEQ 11 if !PY_MINOR! LEQ 14 set "PY_IN_RANGE=1"
    if "!PY_IN_RANGE!"=="0" (
        echo [WARN] Python !PY_VERSION! est hors de la plage officiellement testee de ce projet ^(3.11-3.14^).
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
    "!PYTHON_EXE!" !PYTHON_ARGS! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [WARN] Standard venv failed, trying virtualenv fallback...
        "!PYTHON_EXE!" !PYTHON_ARGS! -m pip install --user virtualenv
        if errorlevel 1 (
            echo [ERROR] Failed to install virtualenv fallback.
            pause
            exit /b 1
        )
        "!PYTHON_EXE!" !PYTHON_ARGS! -m virtualenv "%VENV_DIR%"
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
    echo [HINT] for this Python version. Use Python 3.11-3.14, or check pypi.org for
    echo [HINT] wheel availability before retrying.
    pause
    exit /b 1
)

echo [SUCCESS] Environment is ready.
endlocal

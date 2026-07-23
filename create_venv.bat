@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

echo [INFO] Working directory: %CD%

echo [INFO] Detecting installed Python version...
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PY_VERSION="

REM `py` et `python` presents sur le PATH sont souvent les raccourcis Microsoft Store :
REM ils affichent un message d'aide, ne lancent aucun interpreteur, et sortent malgre
REM tout en code 0. Ni `where` ni `errorlevel` ne permettent de les ecarter : chaque
REM candidat doit etre reellement execute avant d'etre retenu (cf. :try_python).
call :try_python "py" "-3"
call :try_python "python" ""

for %%D in (
    "%USERPROFILE%\Anaconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\Miniconda3"
    "%USERPROFILE%\miniconda3"
    "%LOCALAPPDATA%\anaconda3"
    "%LOCALAPPDATA%\miniconda3"
    "C:\ProgramData\Anaconda3"
    "C:\ProgramData\Miniconda3"
    "C:\ProgramData\anaconda3"
    "C:\ProgramData\miniconda3"
    "C:\Users\Public\Anaconda3"
    "C:\Users\Public\Miniconda3"
) do call :try_python "%%~D\python.exe" ""

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try_python "%%~D\python.exe" ""

if not defined PYTHON_EXE (
    echo [ERROR] No working Python interpreter found.
    echo [HINT] Install Python 3.11-3.14, or make sure your existing installation
    echo [HINT] ^(Anaconda/Miniconda included^) has its python.exe reachable from the PATH.
    echo [HINT] Un "python" du PATH qui affiche "Python est introuvable" est un raccourci
    echo [HINT] Microsoft Store : le desactiver dans Parametres ^> Applications ^> Alias
    echo [HINT] d'execution d'application, ou ajouter le vrai Python au PATH.
    pause
    exit /b 1
)

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
exit /b 0

REM Retient le candidat %1 (arguments %2) uniquement si son `--version` renvoie un vrai
REM numero de version 3.x. Les raccourcis Microsoft Store repondent par un message d'aide
REM ("Python est introuvable ...") : c'est le seul critere qui les distingue, leur code de
REM sortie valant 0 comme celui d'un interpreteur reel.
:try_python
if defined PYTHON_EXE goto :eof
set "CAND_EXE=%~1"
set "CAND_ARGS=%~2"
set "CAND_OUT="
if "%CAND_EXE:~1,1%"==":" if not exist "%CAND_EXE%" goto :eof
for /f "tokens=2" %%V in ('"%CAND_EXE%" %CAND_ARGS% --version 2^>^&1') do if not defined CAND_OUT set "CAND_OUT=%%V"
if not defined CAND_OUT goto :eof
if not "!CAND_OUT:~0,2!"=="3." goto :eof
set "PYTHON_EXE=%CAND_EXE%"
set "PYTHON_ARGS=%CAND_ARGS%"
set "PY_VERSION=%CAND_OUT%"
goto :eof

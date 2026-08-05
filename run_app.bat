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

REM Remise a niveau des paquets si requirements.txt a change depuis la derniere installation :
REM sans cela, une mise a jour du code tournerait sur un environnement virtuel obsolete.
python scripts\sync_dependencies.py
if errorlevel 1 (
    echo [WARN] Les dependances n'ont pas pu etre synchronisees automatiquement.
    echo [HINT] L'application est lancee malgre tout ; en cas d'erreur, fermer cette fenetre
    echo [HINT] et relancer create_venv.bat.
)

echo [INFO] Launching Streamlit app...
streamlit run app.py

if errorlevel 1 (
    echo [ERROR] Streamlit execution failed.
    pause
    exit /b 1
)

endlocal

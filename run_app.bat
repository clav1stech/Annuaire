@echo off
REM Lancement de l'application Streamlit principale (Windows).
REM Seul script que l'utilisateur ait a lancer : il installe l'environnement au premier
REM demarrage, le remet a niveau si besoin, puis ouvre l'application.
setlocal
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

REM Premier lancement : l'environnement est cree ici meme, pour que run_app.bat reste le seul
REM script a lancer. L'installation est deleguee a create_venv.bat, qui garde la detection de
REM l'interpreteur Python (alias Microsoft Store, Anaconda, plage de versions supportee).
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Premiere utilisation : installation de l'environnement en cours.
    echo [INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenetre.
    call "%~dp0create_venv.bat"
    if errorlevel 1 (
        REM create_venv.bat a deja affiche l'erreur et son propre pause : ne pas en rajouter.
        echo [ERROR] Installation impossible : l'application ne peut pas demarrer.
        exit /b 1
    )
)

REM Second controle volontaire : create_venv.bat sort en code 0 sans creer d'environnement
REM quand l'utilisateur refuse de continuer avec un Python hors de la plage testee.
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Environnement virtuel absent apres l'etape d'installation.
    echo [HINT] Relancer create_venv.bat pour voir le detail de l'echec.
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
REM Streamlit manquant dans un environnement par ailleurs complet (installation interrompue,
REM dossier bricole) : l'empreinte enregistree ne refletant plus la realite, on reinstalle.
if not exist "%VENV_DIR%\Scripts\streamlit.exe" (
    echo [WARN] Streamlit introuvable dans l'environnement : reinstallation des dependances.
    python scripts\sync_dependencies.py --force
) else (
    python scripts\sync_dependencies.py
)
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

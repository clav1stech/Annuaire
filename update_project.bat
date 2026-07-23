@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_DIR=.venv_annuaire_sirene"

set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
) else (
    REM Meme piege que dans create_venv.bat : un `python`/`py` present sur le PATH peut
    REM etre un raccourci Microsoft Store qui ne lance aucun interpreteur.
    call :try_python "python" ""
    call :try_python "py" "-3"
)

if not defined PYTHON_EXE (
    echo [ERROR] No working Python interpreter found.
    echo [HINT] Run create_venv.bat first, or install Python 3.11-3.14 ^(see README^).
    pause
    exit /b 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% scripts\update_project.py %*

pause
endlocal
exit /b 0

:try_python
if defined PYTHON_EXE goto :eof
set "CAND_EXE=%~1"
set "CAND_ARGS=%~2"
set "CAND_OUT="
for /f "tokens=2" %%V in ('"%CAND_EXE%" %CAND_ARGS% --version 2^>^&1') do if not defined CAND_OUT set "CAND_OUT=%%V"
if not defined CAND_OUT goto :eof
if not "!CAND_OUT:~0,2!"=="3." goto :eof
set "PYTHON_EXE=%CAND_EXE%"
set "PYTHON_ARGS=%CAND_ARGS%"
goto :eof

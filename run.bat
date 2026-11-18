@echo off
rem Lance SerialHex avec l'environnement .venv (sans fenetre de console)
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Environnement .venv absent : lancer setup.bat d'abord.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" serialhex.py %*

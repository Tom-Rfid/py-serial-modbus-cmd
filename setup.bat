@echo off
rem Prepare l'environnement Python (.venv). Arguments transmis a setup.ps1 :
rem   setup.bat                 Python 3.9 (minimum du debogueur VS Code)
rem   setup.bat -Python 3.12    autre version
rem   setup.bat -Recreate       environnement neuf
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
pause

@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo HOVER: no encontre .venv. Ejecuta INSTALAR_WINDOWS.bat.
    exit /b 1
)
".venv\Scripts\python.exe" -m hover_next.launch_background
exit /b %errorlevel%

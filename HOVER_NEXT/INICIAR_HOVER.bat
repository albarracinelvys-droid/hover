@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo [HOVER] Falta el entorno virtual. Ejecuta INSTALAR_WINDOWS.bat primero.
  exit /b 1
)
".venv\Scripts\python.exe" -m hover_next.launch_background --engine auto --threshold 0.0008
exit /b %errorlevel%

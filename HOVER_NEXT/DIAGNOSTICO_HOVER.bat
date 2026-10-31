@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo HOVER: no encontre el entorno Python.
    exit /b 1
)
".venv\Scripts\python.exe" -m hover_next.diagnostics
exit /b %errorlevel%

@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - Pruebas simuladas, sin abrir aplicaciones
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "PROBAR_HOVER_V4_3.py"
) else (
  python "PROBAR_HOVER_V4_3.py"
)
pause

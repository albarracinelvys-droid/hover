@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - Prueba de comandos reales por texto
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "Asistente_Voz_HOVER_v4_3.py" --texto
) else (
  python "Asistente_Voz_HOVER_v4_3.py" --texto
)
pause

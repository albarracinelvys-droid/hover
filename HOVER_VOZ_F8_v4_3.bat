@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - F8 contra ruido ambiental
if not exist ".venv\Scripts\python.exe" (
  echo Instala primero INSTALAR_VOZ_HOVER_v4_3.bat
  pause
  exit /b 1
)
echo Pulsa F8 para dictar una orden. No necesitas decir Oye Hover.
".venv\Scripts\python.exe" "Asistente_Voz_HOVER_v4_3.py" --motor whisper --tamano small --solo-f8 --hablar
pause

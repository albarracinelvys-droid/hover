@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - Whisper Small
if not exist ".venv\Scripts\python.exe" (
  echo Instala primero INSTALAR_VOZ_HOVER_v4_3.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "Asistente_Voz_HOVER_v4_3.py" --motor whisper --tamano small --hablar
pause

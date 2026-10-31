@echo off
chcp 65001 >nul
title HOVER - Vosk 4.1 (motor ligero)
cd /d "%~dp0"
py -3 Asistente_Voz_HOVER_v4_1.py --motor vosk --hablar
if errorlevel 1 (
  echo Asegurate de haber instalado el modelo en la carpeta modelo-es.
  pause
)

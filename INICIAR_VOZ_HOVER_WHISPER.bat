@echo off
chcp 65001 >nul
title HOVER - reconocimiento por voz Whisper (local)
cd /d "%~dp0"
echo Motor: faster-whisper BASE CPU int8. Primera ejecucion requiere descarga de modelo.
echo Di: Oye Hover, abre ChatGPT.
py -3 Asistente_Voz_HOVER_v4_1.py --motor whisper --tamano base --hablar
if errorlevel 1 (
  echo.
  echo No se pudo iniciar Whisper. Ejecuta INSTALAR_WHISPER_HOVER.bat.
  pause
)

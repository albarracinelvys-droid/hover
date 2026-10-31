@echo off
chcp 65001 >nul
title HOVER - instalar motor de voz Whisper
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No encuentro Python. Instala Python 3.11 o 3.12 con py.exe.
  pause
  exit /b 1
)
echo Instalando faster-whisper, sounddevice y numpy (solo una vez).
py -3 -m pip install --upgrade faster-whisper sounddevice numpy
if errorlevel 1 (
  echo No se pudo instalar Whisper. Revisa la conexion a Internet y la version de Python.
  pause
  exit /b 1
)
echo Listo. Ejecuta INICIAR_VOZ_HOVER_WHISPER.bat.
echo La primera ejecucion descargara el modelo base; despues el reconocimiento es local.
pause

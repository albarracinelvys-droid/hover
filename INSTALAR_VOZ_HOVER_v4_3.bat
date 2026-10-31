@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - Instalador de voz local
if not exist ".venv\Scripts\python.exe" (
  py -3.13 -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No se pudo crear el entorno de Python.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "faster-whisper>=1.2" "sounddevice>=0.5" "numpy>=1.26"
if errorlevel 1 (
  echo [ERROR] No se pudieron instalar las dependencias.
  pause
  exit /b 1
)
echo.
echo [OK] Preparado. Inicia HOVER_INICIAR_VOZ_v4_3.bat
pause

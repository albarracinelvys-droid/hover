@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HOVER 4.3 - Control de Spotify dirigido a su sesion de Windows
if not exist ".venv\Scripts\python.exe" (
 echo Ejecuta primero INSTALAR_VOZ_HOVER_v4_3.bat
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install "winrt-Windows.Media.Control"
if errorlevel 1 (
 echo [AVISO] No se pudo instalar el controlador. HOVER seguira usando el puente multimedia cuando exista.
 pause
 exit /b 1
)
echo [OK] Control dirigido a Spotify instalado en el entorno HOVER.
pause

@echo off
chcp 65001 >nul
title HOVER - Instalar puente multimedia
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo HOVER necesita Python 3.11 o posterior para mostrar caratulas y metadatos.
  echo Instala Python con el lanzador py y ejecuta este archivo de nuevo.
  pause
  exit /b 1
)
py -3 -m pip install --upgrade "winrt-Windows.Media.Control" "winrt-Windows.Media" "winrt-Windows.Storage.Streams"
if errorlevel 1 (
  echo No se pudieron instalar las dependencias.
  pause
  exit /b 1
)
echo Instalacion terminada. Ejecuta INICIAR_PUENTE_HOVER.bat.
pause

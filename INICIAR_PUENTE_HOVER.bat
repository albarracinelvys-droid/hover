@echo off
chcp 65001 >nul
title HOVER - Puente multimedia
cd /d "%~dp0"
py -3 Puente_HOVER_v3_9_2.py
if errorlevel 1 (
  echo Fallo el puente. Revisa las dependencias o ejecuta INSTALAR_PUENTE_HOVER.bat.
  pause
)

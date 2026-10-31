@echo off
chcp 65001 >nul
title HOVER - Whisper SMALL (mas preciso, mas lento)
cd /d "%~dp0"
py -3 Asistente_Voz_HOVER_v4_1.py --motor whisper --tamano small --hablar
if errorlevel 1 pause

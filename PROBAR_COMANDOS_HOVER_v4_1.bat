@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 Asistente_Voz_HOVER_v4_1.py --texto
pause

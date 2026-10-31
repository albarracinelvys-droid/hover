@echo off
cd /d "%~dp0"
echo HOVER prueba: F8 y "abre calculadora". No hace falta decir Hover.
".venv\Scripts\python.exe" -m hover_next.app --voice --engine auto --mic 1 --threshold 0.0008
pause

@echo off
cd /d "%~dp0"
echo HOVER: asistente silencioso. Mantenga este programa abierto.
echo Usa el microfono Realtek predeterminado dispositivo 1.
".venv\Scripts\python.exe" -m hover_next.app --voice --model small --mic 1 --threshold 0.0008
pause

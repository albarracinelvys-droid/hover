@echo off
cd /d "%~dp0"
REM Segun lista de dispositivos aportada para esta prueba: micrófono Realtek WASAPI #9
REM Si Windows cambia los indices, reemplaza 9 por el valor actualizado.
".venv\Scripts\python.exe" -m hover_next.app --voice --model small --mic 9 --threshold 0.0006
pause

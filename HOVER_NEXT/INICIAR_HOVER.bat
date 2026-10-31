@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo HOVER v5 - motor silencioso inspirado en Coucou.
echo Di "Hover, abre calculadora" o pulsa F8 y di "abre calculadora".
echo Parakeet se usa cuando esta instalado; de lo contrario Whisper.
".venv\Scripts\python.exe" -m hover_next.app --voice --engine auto --model small --mic 1 --threshold 0.0008
if errorlevel 1 echo ERROR: revisa el mensaje anterior.
pause

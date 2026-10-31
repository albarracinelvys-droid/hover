@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.app --voice --model small --mic 9 --threshold 0.0006
pause

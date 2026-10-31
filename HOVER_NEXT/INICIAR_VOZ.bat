@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.app --voice --model small
pause

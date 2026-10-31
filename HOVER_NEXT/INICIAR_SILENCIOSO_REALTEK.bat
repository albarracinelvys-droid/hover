@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.launch_background --engine auto --mic 9 --threshold 0.0006
exit /b %errorlevel%

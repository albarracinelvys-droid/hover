@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.launch_background --engine auto --threshold 0.0008
exit /b %errorlevel%

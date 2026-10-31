@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.setup_project chatgpt zap
pause

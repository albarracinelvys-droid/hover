@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m hover_next.launch_background --stop
if errorlevel 1 (
  echo HOVER: revisa el mensaje anterior.
  pause
)

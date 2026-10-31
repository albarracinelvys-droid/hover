@echo off
cd /d "%~dp0"
echo HOVER - modo de diagnostico con consola visible.
".venv\Scripts\python.exe" -m hover_next.app --voice --model small
if errorlevel 1 echo HOVER: revisa el error anterior.
pause

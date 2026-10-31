@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if errorlevel 1 (
 echo ERROR creando entorno virtual. Instala Python 3.11 o 3.12.
 pause
 exit /b 1
)
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
call ".venv\Scripts\python.exe" -m playwright install chromium
echo.
echo INSTALADO. El primer uso de Whisper descargara un modelo.
pause

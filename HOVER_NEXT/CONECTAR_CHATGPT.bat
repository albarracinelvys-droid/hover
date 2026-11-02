@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero instala las dependencias de HOVER.
  pause
  exit /b 2
)
echo Usa este asistente SOLO con HOVER detenido. Inicio de sesion manual.
".venv\Scripts\python.exe" -m hover_next.chat_login
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" echo Revisa el navegador e intenta otra vez.
pause
exit /b %RESULT%

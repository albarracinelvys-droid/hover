@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo HOVER - Prueba REAL de acciones de Windows SIN microfono.
echo Deberian abrirse Calculadora, ChatGPT y Google.
echo.
".venv\Scripts\python.exe" -m hover_next.app --text "abre calculadora"
if errorlevel 1 echo ERROR: Calculadora.
echo.
".venv\Scripts\python.exe" -m hover_next.app --text "ChatGPT"
if errorlevel 1 echo ERROR: ChatGPT.
echo.
".venv\Scripts\python.exe" -m hover_next.app --text "abre una nueva pestana de Google"
if errorlevel 1 echo ERROR: Google.
echo.
echo Si se abrieron las tres, la ejecucion funciona y solo hay que probar el microfono.
echo Si NO se abrieron, copia la salida de esta ventana para diagnostico.
pause

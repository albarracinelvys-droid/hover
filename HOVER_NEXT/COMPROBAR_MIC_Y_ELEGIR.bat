@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo HOVER - verifica cual microfono entiende tu voz de verdad.
echo Repite "Hover abre calculadora" en las dos pruebas.
echo No guardamos audio; solo el numero del microfono que funcione.
echo.
".venv\Scripts\python.exe" -m hover_next.voice_check --devices 1,9
pause

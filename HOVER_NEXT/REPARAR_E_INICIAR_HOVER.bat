@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo HOVER 5.0 - reinstalacion del motor de voz local Coucou Parakeet.
echo Solo la primera instalacion descarga ~670 MB.
echo.
if not exist ".venv\Scripts\python.exe" (
 call INSTALAR_WINDOWS.bat
)
call INSTALAR_MOTOR_COUCOU_HOVER.bat
if errorlevel 1 (
 echo No se instalo Parakeet, se intentara Whisper existente.
)
echo.
echo Iniciando HOVER. Usa F8 si la palabra de activacion falla.
call INICIAR_HOVER.bat

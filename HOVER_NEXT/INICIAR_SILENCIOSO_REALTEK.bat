@echo off
setlocal
cd /d "%~dp0"
echo Para seleccionar Realtek manualmente usa INICIAR_VOZ_CONSOLA.bat
call ".\INICIAR_VOZ.bat"
exit /b %errorlevel%

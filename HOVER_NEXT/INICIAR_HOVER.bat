@echo off
setlocal
cd /d "%~dp0"
call ".\INICIAR_VOZ.bat"
exit /b %errorlevel%

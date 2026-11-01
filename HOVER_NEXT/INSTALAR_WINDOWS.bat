@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
  echo [HOVER] Creando entorno virtual...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :venv_error
)

echo [HOVER] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_error
echo [HOVER] Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error
echo [HOVER] Instalando Chromium para Playwright...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :install_error

echo.
echo [HOVER] Instalacion completada. El primer uso de Whisper puede descargar un modelo.
exit /b 0

:venv_error
echo [HOVER] ERROR: No se pudo crear el entorno virtual. Instala Python 3.11 o 3.12.
exit /b 1

:install_error
echo [HOVER] ERROR: Instalacion incompleta. Revisa los mensajes de pip/Playwright.
exit /b 1

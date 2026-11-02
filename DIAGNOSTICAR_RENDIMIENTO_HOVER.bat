@echo off
setlocal
set "HOVER_LOG=%LOCALAPPDATA%\HOVER_NEXT\voice.log"
if not exist "%HOVER_LOG%" (
  echo [HOVER] No existe un registro de voz local.
  exit /b 1
)
echo [HOVER] Ultimas 25 mediciones locales en milisegundos:
powershell -NoProfile -Command "Select-String -LiteralPath $env:HOVER_LOG -Pattern '^\[latencia\]' | Select-Object -Last 25 | ForEach-Object { $_.Line }"
echo.
echo [HOVER] No compartas el log completo: puede contener textos personales.
exit /b 0

@echo off
chcp 65001 >nul
title HOVER - Instalar asistente de voz
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Instala Python 3.11 o 3.12 desde python.org incluyendo el lanzador py.
 pause
 exit /b 1
)
py -3 -m pip install --upgrade vosk sounddevice
if errorlevel 1 (
 echo Fallo la instalacion de Vosk o del microfono.
 pause
 exit /b 1
)
if exist "%~dp0modelo-es" (
 echo Modelo espanol existente. No se descarga de nuevo.
 goto listo
)
echo.
echo Para reconocer espanol SIN Internet al usar HOVER, descarga el modelo
 echo Vosk pequeno de ~40 MB desde alphacephei.com al instalarlo una vez.
echo.
choice /c SN /n /m "Descargar modelo oficial espanol de Vosk ahora? [S/N] "
if errorlevel 2 goto manual
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $u='https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip'; $zip=Join-Path (Get-Location) 'hover-modelo-es.zip'; Invoke-WebRequest -Uri $u -OutFile $zip; Expand-Archive -Path $zip -DestinationPath '.' -Force; Remove-Item $zip; if(Test-Path 'vosk-model-small-es-0.42'){Rename-Item 'vosk-model-small-es-0.42' 'modelo-es'}"
if errorlevel 1 goto manual
if not exist "%~dp0modelo-es" goto manual
goto listo
:manual
echo Descarga un modelo ESPANOL manualmente de https://alphacephei.com/vosk/models
echo Extrae su contenido en la carpeta: "%~dp0modelo-es"
pause
exit /b 1
:listo
echo Instalacion terminada.
echo Ejecuta INICIAR_VOZ_HOVER.bat cuando quieras habilitar el microfono.
pause

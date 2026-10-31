@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo HOVER - Parakeet local (modelo usado por Coucou Windows)
echo Descarga inicial ~670 MB. Solo se necesita una vez.
echo Comprueba espacio disponible y conexion a internet.
echo.
".venv\Scripts\python.exe" -m pip install --upgrade sherpa-onnx huggingface_hub
if errorlevel 1 (
 echo ERROR instalando sherpa-onnx. Comprueba la version de Python.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m hover_next.app --install-parakeet
if errorlevel 1 (
 echo ERROR descargando el modelo. No se cambiaron tus archivos personales.
 pause
 exit /b 1
)
echo.
echo Motor Parakeet instalado. Inicia INICIAR_HOVER.bat.
pause

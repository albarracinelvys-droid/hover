@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   HOVER - INSTALAR MODELO LOCAL DE LENGUAJE NATURAL
echo ========================================================
echo.
where ollama >nul 2>nul
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    ) else (
        echo Ollama no esta instalado. Instalando con Windows Package Manager...
        where winget >nul 2>nul
        if errorlevel 1 (
            echo ERROR: No hay winget. Instala Ollama desde https://ollama.com/download/windows
            pause
            exit /b 2
        )
        winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
        if errorlevel 1 (
            echo ERROR: Ollama no se pudo instalar. Visita https://ollama.com/download/windows
            pause
            exit /b 2
        )
        set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    )
) else (
    set "OLLAMA=ollama"
)
echo.
echo Preparando Qwen 2.5 (3B), local en tu Windows...
call "%OLLAMA%" pull qwen2.5:3b
if errorlevel 1 (
    echo ERROR: No se pudo descargar el modelo. Comprueba Ollama y la conexion.
    pause
    exit /b 2
)
echo.
echo MODELO DESCARGADO. Probando interpretacion sin ejecutar acciones...
if not exist ".venv\Scripts\python.exe" (
    echo Falta entorno Python de HOVER. Primero instala HOVER.
    pause
    exit /b 2
)
echo Preparando las dependencias locales de HOVER...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias de HOVER.
    pause
    exit /b 2
)
".venv\Scripts\python.exe" -m hover_next.nlu_check
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo Ollama se instalo, pero el interprete todavia no responde.
    echo Comprueba que Ollama este abierto en Windows y ejecuta de nuevo.
) else (
    echo.
    echo LISTO. Inicia HOVER con INICIAR_VOZ.bat
)
echo.
pause
exit /b %CODE%

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo HOVER - Google OAuth 2.0 en Windows
echo Las credenciales y tokens NO se suben a GitHub.
echo.
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: primero instala HOVER con INSTALAR_WINDOWS.bat
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-google.txt
if errorlevel 1 (
 echo ERROR: revisa el error de dependencias de Google.
 pause
 exit /b 1
)
if not exist "%LOCALAPPDATA%\HOVER_NEXT\google_oauth_client.json" (
 echo.
 echo FALTA el archivo OAuth local del usuario:
 echo %LOCALAPPDATA%\HOVER_NEXT\google_oauth_client.json
 echo Crea el cliente OAuth de tipo Aplicacion de escritorio
 echo desde Google Cloud Console y copialo ahi.
 if not exist "%LOCALAPPDATA%\HOVER_NEXT" mkdir "%LOCALAPPDATA%\HOVER_NEXT"
 start "" "%LOCALAPPDATA%\HOVER_NEXT"
)
echo.
echo Listo para la autorizacion. Ejecuta INICIAR_HOVER.bat.
echo En Windhawk v4.6 abre Atajos y pulsa GOOGLE.
pause

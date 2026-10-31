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
 echo.
 echo Abre https://console.cloud.google.com/auth/clients
 echo Crea cliente OAuth de tipo Aplicacion de escritorio.
 echo Descarga el JSON y renombralo google_oauth_client.json.
 echo Copialo a la carpeta que acabamos de abrir.
 echo NO escribas contrasenas ni tokens en google_control.txt.
 if not exist "%LOCALAPPDATA%\HOVER_NEXT" mkdir "%LOCALAPPDATA%\HOVER_NEXT"
 start "" "%LOCALAPPDATA%\HOVER_NEXT"
 echo.
 echo Google NO esta conectado ni listo sin ese archivo.
 pause
 exit /b 2
)
".venv\Scripts\python.exe" -c "from hover_next.google_auth import _client_path; _client_path(); print('Archivo OAuth de escritorio verificado.')"
if errorlevel 1 (
 echo ERROR: El archivo OAuth no es valido. Descarga un cliente Escritorio.
 pause
 exit /b 2
)
echo.
echo Google OAuth listo para solicitar autorizacion en el navegador.
echo Ejecuta INICIAR_HOVER.bat; en Windhawk v4.6 abre Atajos - GOOGLE.
pause

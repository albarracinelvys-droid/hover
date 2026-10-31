@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==================================================
echo  HOVER - CONEXION REAL DE GOOGLE DRIVE
echo ==================================================
echo.
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: No se encontro Python en .venv.
 echo Ejecuta INSTALAR_WINDOWS.bat para preparar el proyecto.
 pause
 exit /b 2
)
echo Verificando Google OAuth y pywin32...
".venv\Scripts\python.exe" -m pip install -r requirements-google.txt
if errorlevel 1 (
 echo ERROR: Fallo la instalacion de dependencias de Google.
 pause
 exit /b 2
)
echo.
".venv\Scripts\python.exe" -m hover_next.google_cli --service drive
set "HOVER_GOOGLE_EXIT=%ERRORLEVEL%"
echo.
if not "%HOVER_GOOGLE_EXIT%"=="0" (
 echo No se pudo confirmar la conexion. Lee RESULTADO arriba.
 echo Si aparece un error de Windows DPAPI, comprueba que la
 echo autorizacion se hizo con el mismo usuario de Windows.
) else (
 echo Google Drive verificado. Ahora puedes iniciar HOVER.
)
echo.
pause
exit /b %HOVER_GOOGLE_EXIT%

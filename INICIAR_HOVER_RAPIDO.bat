@echo off
setlocal
REM Perfil ligero, sin desactivar las funciones de Google, voz o Spotify.
set "HOVER_WHISPER_MODEL=base"
set "HOVER_WHISPER_BEAM=2"
set "HOVER_NLU_TIMEOUT=6"
set "HOVER_VAD_PAUSE_MS=450"
call "%~dp0DETENER_HOVER.bat"
if errorlevel 1 (
  echo [HOVER] La instancia anterior sigue cerrandose. Reintenta.
  exit /b 1
)
call "%~dp0INICIAR_HOVER.bat"
exit /b %errorlevel%

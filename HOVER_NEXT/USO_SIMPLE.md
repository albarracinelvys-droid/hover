# HOVER — Asistente personal sencillo

Mantiene tu isla de Windhawk. No utiliza voz sintetizada, pitidos ni Codex para tareas diarias.

## Actualizar y ejecutar

```powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INSTALAR_WINDOWS.bat
.\PROBAR.bat
.\INICIAR_HOVER.bat
```

**Para mantener HOVER escuchando:** deja abierto `INICIAR_HOVER.bat`.
Elige `INICIAR_SILENCIOSO_REALTEK.bat` si prefieres el micrófono WASAPI
9 en lugar del dispositivo MME 1. `Ctrl+C` detiene el asistente.

## Ejemplos

- «Hover, abre calculadora»
- «Hover, crea un nuevo documento de Word»
- «Hover, abre Word»
- «Hover, abre Excel»
- «Hover, abre este documento» (selecciona uno en el Explorador antes)
- «Hover, abre el documento Taller 3» (busca por nombre en carpetas locales)
- «Hover, abre Google Drive»
- «Hover, abre Gmail»
- «Hover, abre mi calendario»
- «Hover, crea un documento de Google»
- «Hover, crea una hoja de cálculo»
- «Hover, abre Google Maps»
- «Hover, abre YouTube»
- «Hover, abre una nueva pestaña de Claude y escríbele lo siguiente: Hola»
- «Hover, abre ChatGPT en proyecto Zap y escribe lo siguiente: Necesito un resumen técnico»
- «Hover, abre ChatGPT en proyecto Zap y escribe lo siguiente en un nuevo chat»;
  HOVER abre el destino y espera **tu siguiente frase** como dictado.

### Proyecto Zap (configurar una sola vez)

Ejecuta `CONFIGURAR_PROYECTO_ZAP.bat` y pega la URL exacta de tu proyecto de
ChatGPT, tomada del navegador después de abrirlo. La URL se guarda solamente
en `%LOCALAPPDATA%\HOVER_NEXT\config.json`, nunca en GitHub.
Si el proyecto no está configurado, HOVER **no abrirá un chat general** en
su lugar.

### Microsoft Word, Excel, PowerPoint

Para crear documentos verdaderos en Microsoft Office instalado, HOVER
utiliza la automatización COM de Windows. Ejecuta `INSTALAR_WINDOWS.bat`
de nuevo para instalar el paquete `pywin32` (en Windows).
Si no tienes Office instalado, HOVER explica el problema. No sustituye
Word por Google Docs sin avisar.

### ChatGPT y Claude

HOVER abre un perfil de Chrome independiente controlado por Playwright,
para no interferir con las demás pestañas de tu navegador personal.
**Inicia sesión una vez dentro de ese Chrome**. Es necesario iniciar
sesión para enviar los mensajes y utilizar los proyectos. Las interfaces
de ChatGPT y Claude cambian: puede ser necesario ajustar los selectores.
El programa escribe el texto y pulsa Enter; todavía no confirma la
recepción efectiva por el servidor. Las conversaciones de proyecto
pueden requerir una adaptación adicional del botón de «nuevo chat».

### Google

Abre servicios web de Google con tu navegador predeterminado, usando las
cuentas en las que ya hayas iniciado sesión. Los enlaces de creación
de Docs/Sheets abren sus respectivas páginas de nuevo documento.
**No está implementado todavía** crear eventos de Calendar, enviar
correos o editar Drive mediante API; esas acciones requieren autorización
específica y confirmación antes de enviar datos.

### Seguridad

No dicta órdenes de PowerShell arbitrarias. Solo abre aplicaciones y
documentos en listas permitidas. No ejecuta archivos .exe ni .ps1 por
nombre. El audio se procesa localmente con Whisper.
La información enviada a ChatGPT o Claude sí pasa a esos servicios.

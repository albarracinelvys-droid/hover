# HOVER NEXT — agente de escritorio experimental

**Estado:** base modular de pruebas. El código de Windhawk y la interfaz antigua no se reemplazan. Este directorio puede clonarse y convertirse luego en un proyecto independiente.

## Qué hay implementado

- Interpretación local de órdenes españolas con lista blanca; sin ejecutar comandos arbitrarios generados por modelos.
- CLI interactiva para probar las frases sin micrófono.
- Reconocimiento local con Whisper Small, activación inicial «Oye Hover».
- Apertura de Chrome controlado por HOVER para ChatGPT y Claude; nueva conversación y proyectos por URL fija.
- Envío experimental de prompts y archivos: requiere confirmación y sesión iniciada en el navegador de HOVER. Las interfaces web cambian; no se garantiza el envío ni la descarga automática de resultados.
- Acciones de Windows: abrir Este equipo, capturas, abrir Spotify (sin garantizar reproducción).
- Archivos: buscar archivos en Descargas, copiar o mover a carpeta configurada, con confirmación y sin sobrescribir nombres.
- Crear repositorios privados vía GitHub CLI y confirmación, **solo cuando gh esté instalado y autenticado**.

**No implementado todavía:** gestión completa de respuestas y adjuntos devueltos por Claude/ChatGPT; lectura arbitraria de proyectos sin URL; OAuth de calendario; control preciso de Spotify; creación de tabs inteligentes dentro del mod Windhawk, navegación entre apps por voz sin contexto, operación autónoma de GUI de terceros. Este código no debe llamarse un asistente completo de producción.

## Instalación

En PowerShell:

```powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INSTALAR_WINDOWS.bat
.\PROBAR.bat
.\INICIAR_TEXTO.bat
```

Después ejecuta `INICIAR_VOZ.bat`. Recomendamos Python 3.11 o 3.12 y un micrófono cercano; Whisper descarga el modelo la primera vez.

## Configuración

Crea `%LOCALAPPDATA%\HOVER_NEXT\config.json` y edita:

```json
{
  "downloads": "C:\\Users\\gomez\\Downloads",
  "folder": "C:\\Users\\gomez\\Documents\\HoverRecibidos",
  "projects": {
    "chatgpt": {"zap": "https://chatgpt.com/g/g-example"},
    "claude": {"trabajo": "https://claude.ai/project/REEMPLAZAR"}
  }
}
```

Las URLs mostradas son ejemplos: copia la URL real de cada proyecto. No incluyas contraseñas ni tokens en configuración. Chrome abre un perfil independiente en %LOCALAPPDATA%\HOVER_NEXT\chrome_profile para que inicies sesión manualmente. Ese perfil no debe subirse a Git.

## Ejemplos de comandos

- «Oye Hover, abre ChatGPT»
- «Oye Hover, crea un nuevo chat en Claude»
- «Oye Hover, accede al proyecto de ChatGPT zap»
- «Oye Hover, toma una captura de pantalla»
- «Oye Hover, muéstrame mi PC»
- «Oye Hover, copia el último archivo de Descargas a mi carpeta configurada»
- «Oye Hover, crea un nuevo repositorio privado llamado hover-prototipo»
- «Oye Hover, adjunta archivo taller2.pdf a Claude»

Antes de enviar archivos, cerrar pestañas, enviar prompts o crear repositorios, HOVER exige un **SI** escrito en la consola. El asistente nunca actúa por reconocimiento de voz únicamente en esas acciones.

## Nuevo repositorio privado (opcional)

La conexión de GitHub de ChatGPT puede leer y escribir archivos en el repositorio actual, pero no está autorizada para crear repositorios nuevos. Hazlo desde PowerShell con [GitHub CLI](https://cli.github.com/):

```powershell
winget install --id GitHub.cli -e
gh auth login
cd C:\Users\gomez\hover
git pull origin main
New-Item -ItemType Directory -Force "$env:USERPROFILE\HOVER-ASSISTANT" | Out-Null
Copy-Item .\HOVER_NEXT\* "$env:USERPROFILE\HOVER-ASSISTANT" -Recurse -Force
cd "$env:USERPROFILE\HOVER-ASSISTANT"
git init -b main
git add .
git commit -m "Inicial: HOVER asistente modular"
gh repo create HOVER-ASSISTANT --private --source . --remote origin --push
```

Comprueba con `gh repo view --json name,visibility` que el repositorio sea PRIVADO. El anterior `albarracinelvys-droid/hover` **sigue siendo publico** y contiene una copia del codigo base de HOVER_NEXT (no secretos).

## Arquitectura

`intent.py`: interpreta sin IA y produce acciones permitidas.
`executor.py`: realiza acciones y exige confirmación.
`browser.py`: Chrome controlado por Playwright, sin acceso a tu Chrome cotidiano.
`voice.py`: transcripción local mediante Whisper.
`app.py`: consola de control.
`tests/`: pruebas de regresión.

## Seguridad y límites

- Los modelos Whisper no autentican la voz de quien habla; en entornos ruidosos usa primero `INICIAR_TEXTO.bat`.
- Enviar datos a ChatGPT/Claude comparte esos archivos con esos servicios; revisa privacidad y confirma antes.
- Nunca se ejecutan comandos PowerShell arbitrarios dictados por voz.
- Las acciones web pueden fallar si cambia el HTML o hay un CAPTCHA.
- No se automatiza la extracción de respuestas ni la descarga de entregables terminados.


## Diagnóstico de «Oye Hover»

Whisper puede transcribir «Oye, ¿jover?» o «¡Huji Hover!». El módulo
`hover_next/wake.py` admite esas variantes al principio de la frase.
Verás `[listening]` y escucharás un pitido corto en Windows.

**Importante:** mantén `INICIAR_VOZ.bat` abierto; `INICIAR_TEXTO.bat`
no utiliza el micrófono. La captura se realiza en bloques de cinco segundos,
por lo que no es instantánea. `Ctrl+C` detiene el programa normalmente.
El detector no autentica quién habla y no debería tener permisos para
ejecutar operaciones peligrosas sin confirmación.

Si ves «Reconocido» pero no «[listening]», copia la transcripción exacta
para crear otra prueba de regresión.

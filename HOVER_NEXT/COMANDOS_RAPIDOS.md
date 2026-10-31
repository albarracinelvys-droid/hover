## Correcciones de cierre y carpeta favorita (31 de octubre de 2026)

El motor de voz mantiene Whisper y los controles existentes; el navegador
automatizado se crea y cierra en el mismo hilo para evitar el error
\`greenlet.error: Cannot switch to a different thread\` al pulsar Ctrl+C.

**Consultas y búsquedas:** no piden confirmar con SI.

**Crear un repositorio privado**: aparece una ventana de confirmación de
Windows con el nombre reconocido; confirma solo si coincide exactamente.
Ya no se usa \`input()\` dentro del hilo de reconocimiento. El repositorio
requiere GitHub CLI instalado y autenticado.

**Carpeta seleccionada en la isla:** usa el destino que Windhawk guarda en
\`%APPDATA%\HOVER\carpeta_favorita.txt\` (UTF-16). Selecciónalo desde
Atajos con clic derecho en **Carpeta**, si todavía no lo hiciste.

Ejemplos:
- «Hover, en la carpeta que tienes anexada, crea un TXT llamado prueba1».
- «Hover, crea una subcarpeta llamada prueba uno».
- «Hover, en la carpeta que tienes anexada, crea un documento Excel
  que se llame ProEva1» (requiere Excel instalado).
- «Hover, crea un documento en Google» (abre Google Docs, **no** guarda
  el documento en la carpeta local).
- «Hover, pregúntale a ChatGPT cómo está» (envío sin confirmar).

Un archivo o carpeta que ya existe **nunca se sobrescribe**.
Si Whisper no entiende con claridad el nombre de la carpeta o archivo,
HOVER pedirá una frase más específica.

Para actualizar:
\`\`\`powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INICIAR_HOVER.bat
\`\`\`


---
# HOVER — Comandos de voz cotidianos

Los comandos funcionan con `Hover` u `Oye Hover`, y no necesitan
sintetizador de voz. El resultado se muestra en consola y en la isla.
Ejemplo: «Hover, abre GitHub».

## Apps y Windows
- «Hover, abre calculadora»
- «Hover, abre Bloc de notas»
- «Hover, abre Word»
- «Hover, crea un nuevo documento de Excel»
- «Hover, abre PowerPoint»
- «Hover, abre el administrador de tareas»
- «Hover, abre el explorador de archivos»
- «Hover, abre Descargas»
- «Hover, abre la terminal»
- «Hover, abre la configuración de Windows»
- «Hover, abre este documento» (seleccionado en Explorador)

## Web y Google
- «Hover, abre GitHub»
- «Hover, abre WhatsApp»
- «Hover, abre LinkedIn»
- «Hover, abre Canva»
- «Hover, abre OneDrive»
- «Hover, abre Google Drive»
- «Hover, abre Gmail»
- «Hover, crea una hoja de cálculo»
- «Hover, crea un documento de Google»
- «Hover, abre YouTube»
- «Hover, abre ChatGPT»
- «Hover, abre Claude»

## Preguntas a ChatGPT y Claude por voz

- «**Oye Hover, abre ChatGPT y pregúntale cómo está**»: abre una
  conversación nueva de ChatGPT y escribe **¿Cómo estás?**, después
  pulsa Enter en el cuadro del chat.
- «**Hover, abre Claude y pregúntale qué es un PLC**»: prepara una
  conversación nueva y envía esa pregunta.
- «**Hover, abre chat, repete y pregúntale cómo está**»: acepta la
  transcripción errónea «chat, repete» que produce Whisper.
- «**Hover, abre ChatGPT en proyecto Zap y escribe lo siguiente:
  revisa mi automatización**»: utiliza el proyecto guardado en Atajos.
- «**Hover, abre ChatGPT y escribe lo siguiente**»: abre el chat y
  escucha el mensaje que dictes a continuación.

**Importante:** para escribir preguntas, HOVER controla una ventana
de **Chrome independiente**. Inicia sesión en ChatGPT/Claude allí una
primera vez. La apertura de sitios sencillos utiliza tu navegador
predeterminado, pero los envíos automatizados necesitan esa sesión.
Si no encuentra el cuadro de escritura, mostrará un error en la consola.
Pulsar Enter en el editor no confirma por sí solo la recepción de
la respuesta por el servidor; verifica el chat en el navegador.

## Multimedia (controles globales de Windows)
- «Hover, pausa la música»
- «Hover, siguiente canción»
- «Hover, canción anterior»
- «Hover, sube el volumen»
- «Hover, baja el volumen»
- «Hover, silencia»

Las teclas multimedia actúan sobre el reproductor activo que Windows elija.
No garantizan reproducir una canción concreta en Spotify.

## GitHub, repositorios y seguridad
Ejemplo: «Hover, crea un nuevo repositorio privado en GitHub que se llama
materia-nula».

Se requiere tener instalado **GitHub CLI**, y haber iniciado sesión una vez:

```powershell
winget install --id GitHub.cli -e
gh auth login
```

HOVER muestra el nombre que entendió y pide que lo escribas exactamente en
la consola antes de crearlo. Esto evita que una transcripción incorrecta
cree un repositorio con un nombre distinto al que querías. Nunca crea un
repositorio público por esta ruta.

## Ejecutar
```powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INICIAR_HOVER.bat
```

Di «Hover, qué puedes hacer» para consultar las capacidades más comunes
sin salir del asistente.

**Límites:** las órdenes sobre proyectos de ChatGPT/Claude que requieren
interactuar con sus campos siguen usando automatización de navegador.
Deben verificarse con sesión iniciada. Los comandos web comunes solamente
abren sitios en el navegador existente; no realizan cambios automáticos
dentro de esos sitios.

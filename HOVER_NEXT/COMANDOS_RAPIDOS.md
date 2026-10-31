# HOVER — Recuperación del diálogo y Spotify

La voz local sigue usando el motor que ya reconocía tus frases; no se
cambió el diseño de Windhawk ni se reinstala Whisper.

**Frases de prueba recomendadas:**

- «Hover, abre calculadora».
- «Hover, busca carros baratos en Google».
- «Hover, crea un TXT en la carpeta favorita».
  HOVER mostrará **«Dime solo el nombre para TXT»**. Puedes responder
  «prueba uno» **sin repetir Hover**. No sobrescribe archivos existentes.
- «Hover, crea un repositorio privado en GitHub».
  HOVER pedirá el nombre en la isla. Responde «prueba uno» y continuará
  con la creación privada autorizada por voz. Solo funciona si GitHub CLI
  ya está instalado y autenticado.
- Si Whisper transcribe «que ya me prueba uno» o «que llame PRA1»,
  HOVER **no crea un repositorio posiblemente mal nombrado**: pide el
  nombre de nuevo para que lo dictes claramente.
- «Hover, reproduce Spotify».
  HOVER abre Spotify y **solicita reproducir** mediante la sesión
  multimedia de Windows si está disponible; de lo contrario envía
  el botón multimedia reproducir/pausar. Este último es un control
  alternante, así que no garantiza que suene una canción si Spotify no
  tiene una pista seleccionada.
- Tras abrir Spotify, «Reprodúcelo» funciona durante los siguientes
  45 segundos sin repetir Hover. Si ya hay música sonando, usar el
  control alternante podría pausarla.
- Mientras HOVER está conversando contigo, si Whisper pierde «Hover»
  pero entiende «Oye, crea un TXT ...», admite esa nueva instrucción
  siempre que sea una operación segura y esté dentro de esa ventana
  de conversación. Fuera de ella se exige «Hover» o F8.

**Actualizar y probar:**

```powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\INICIAR_HOVER.bat
```

Las pruebas no usan micrófono, cuenta GitHub ni Spotify reales.
Solo validan la lógica y las llamadas al sistema. Para saber si
Spotify reproduce audio efectivamente en tu equipo, hay que
probarlo con una sesión iniciada y una lista o canción disponible.

---

## Correcciones de cierre y carpeta favorita (31 de octubre de 2026)

El motor de voz mantiene Whisper y los controles existentes; el navegador
automatizado se crea y cierra en el mismo hilo para evitar el error
\`greenlet.error: Cannot switch to a different thread\` al pulsar Ctrl+C.

**Consultas y búsquedas:** no piden confirmar con SI.

**Crear un repositorio privado por voz:** si la instrucción incluye claramente
«crea», «repositorio», «privado» y su nombre, se ejecuta sin confirmación.
HOVER abre el enlace real de GitHub en Google Chrome y muestra el
progreso de creación en la isla. «prueba uno en privado» se interpreta
como `prueba-uno`; las frases dudosas mantienen confirmación.
Esto no afecta a compras, pagos ni eliminaciones.

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

**En modo voz no se pide confirmación para repositorios privados con un
nombre claro.** Se ejecuta `gh repo create --private`, se recupera
la URL real y se abre en Chrome (o en el navegador predeterminado).
La isla muestra «Creando», «Buscando URL» y «Abriendo Chrome».
Las transcripciones inseguras conservan la confirmación visual;
los comandos de texto siguen pidiendo confirmación. Nunca se crea
un repositorio público por esta ruta.

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

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

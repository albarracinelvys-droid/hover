## Google OAuth 2.0 — HOVER v4.6

La integración opcional de Gmail, Drive, Calendar y Docs ya está en el
motor Python y en la nueva interfaz **Atajos → GOOGLE**.

**Configuración:** lee la
[guía completa Google OAuth](GUIA_GOOGLE_OAUTH.md).
Necesitarás crear tu propio cliente OAuth de **Aplicación de escritorio**
en Google Cloud y autorizar tu cuenta Google en el navegador. Ningún token
ni archivo OAuth real está publicado en GitHub.

```powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INSTALAR_GOOGLE_HOVER.bat
.\INICIAR_HOVER.bat
```

En Windhawk debes reemplazar el código del mod actual por
[`HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp`](../HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp)
y compilar con Ctrl+B. El motor Python y la isla se actualizan
separadamente; `git pull` solo actualiza los archivos locales.

Las búsquedas públicas siguen utilizando Google Search. Al conectar tu
cuenta HOVER también consulta los servicios privados autorizados y muestra
coincidencias locales; solo envía metadatos a ChatGPT/Claude cuando lo
pides explícitamente y confirmas la transferencia. Las sesiones de ChatGPT
y Claude siguen siendo independientes en Chrome.

**Estado:** tests unitarios e integración simulada con APIs; el inicio
de sesión OAuth y el uso de servicios reales solo pueden validarse
después de conectar tu cuenta en Windows.

---

## Corrección inmediata: reconocimiento correcto pero sin acciones

Los registros mostraron que HOVER transcribía «Hover. ChatGPT»,
«Abre Clouding», «Hover. Clout» y «Abre una nueva pestaña de Google»,
pero los interpretaba como \`unknown\`. **Ya se añadieron reglas para
esas frases reales**. Para tareas sencillas como abrir ChatGPT o Claude,
HOVER ahora utiliza el navegador predeterminado de Windows, sin depender
del perfil automatizado de Playwright.

### Verificar acciones SIN micrófono

En PowerShell:

\`\`\`powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\PROBAR_APERTURA_REAL.bat
\`\`\`

Esta prueba debe intentar abrir **Calculadora, ChatGPT y Google**. Si no
lo hace, envía el texto de la consola: podremos diagnosticar el ejecutor
sin mezclarlo con problemas del micro.

### Comprobar con tu voz

Cierra todos los asistentes antiguos, después ejecuta:

\`\`\`powershell
.\INICIAR_HOVER.bat
\`\`\`

Prueba «Oye Hover, abre calculadora», «Oye Hover, abre Claude» y
«Oye Hover, abre una nueva pestaña de Google».

La consola debe mostrar \`[voz]\` seguido de \`[accion]\` y la respuesta
\`HOVER: ...\`. HOVER no habla ni reproduce pitidos.

\`Oye Hover, cierra Google\` cierra una pestaña **solo si el navegador
con la pestaña Google está en primer plano**. No permite cerrar otras
ventanas por error.

### Parakeet

El modelo debe pasar SHA-256. Si \`joiner.int8.onnx\` falla la comprobación,
el instalador reintenta ese archivo sin volver a descargar el codificador
completo. Para probarlo de nuevo, ejecuta
\`INSTALAR_MOTOR_COUCOU_HOVER.bat\`. **No es obligatorio para comprobar
las acciones:** Whisper sigue siendo un motor alternativo.


---

## MOTOR HOVER 5 — reparación del reconocimiento basada en Coucou Windows

El problema visible en el registro era la transcripción de silencio/ruido
como «¡Suscríbete!» o «Subtítulos ...» y la activación que no se encontraba.
La versión nueva conserva HOVER sin voz ni pitidos y deja intacta la interfaz.

**Se usa la arquitectura de Coucou**, no su personaje: detección de actividad
de voz adaptable al ruido, precaptura, reconocimiento local y máquina de
estados para «Hover», orden y dictado. El código es original para Python.
Coucou Windows usa Parakeet v3 en sherpa-onnx; HOVER admite ese modelo
opcional y mantiene Whisper si todavía no está instalado.

### Recuperación recomendada en este PC

1. Cierra con Ctrl+C todas las terminales antiguas de voz.
2. En PowerShell:
   \`\`\`powershell
   cd C:\Users\gomez\hover
   git pull origin main
   cd .\HOVER_NEXT
   .\REPARAR_E_INICIAR_HOVER.bat
   \`\`\`
3. El instalador descargará **~670 MB una sola vez** si instalas Parakeet,
   comprobará SHA-256 y abrirá HOVER. Se usa el micrófono predeterminado o
   el elegido en la configuración local.
4. Di «Hover, abre calculadora». **Alternativa inmediata:** pulsa F8 y di
   «abre calculadora»; si funciona con F8 pero no con «Hover», la ejecución
   está bien y queda por afinar únicamente el reconocimiento de activación.

Si el asistente sigue transcribiendo palabras inventadas:

\`\`\`powershell
.\COMPROBAR_MIC_Y_ELEGIR.bat
\`\`\`

Di «Hover abre calculadora» en cada una de las dos grabaciones de prueba.
HOVER compara **Realtek 1 y Realtek 9**, muestra lo que cada uno transcribió,
y guarda el mejor índice en
\`%LOCALAPPDATA%\HOVER_NEXT\config.json\` siempre que la coincidencia sea
suficiente. No guarda ni sube el audio de esas pruebas. Después ejecuta
\`INICIAR_HOVER.bat\` normalmente.

### Diferencias técnicas

- La captura de audio y la transcripción trabajan en **hilos separados**.
  Un procesamiento pesado no bloquea la lectura del micrófono.
- **VAD adaptativo**: 30 ms por bloque, 360 ms de precaptura, mínimo 300 ms
  de voz, 750 ms de silencio para terminar frase; filtra impulsos cortos.
- **Ganancia moderada**: compensa volumen bajo sin amplificar silencios
  ilimitadamente.
- **Parakeet TDT 0.6B v3 int8**: pesos oficiales del repositorio referenciado
  por Coucou, revisión fijada y verificación SHA-256 de los cuatro archivos.
- **Whisper Small** sigue disponible como respaldo.
- **F8** permite pedir una orden sin pronunciar «Hover», útil para diagnosticar.
- La consola muestra \`[voz]\`, \`[accion]\`, \`[asr]\` y \`[mic]\` cuando sea
  pertinente. El estado se informa visualmente mediante la isla.
- La gestión de proyectos desde Atajos sigue funcionando como antes.

### Límites

El modelo Parakeet no está incluido en GitHub por su tamaño y debe descargarse
en el computador. Todavía no tenemos una prueba de ejecución sobre el micrófono
Realtek ni sobre el navegador real; las pruebas CI son de lógica y de audio
sintético. Si la calidad del dispositivo es insuficiente, la selección guiada
de micrófono será necesaria. Por seguridad, el dictado no autoriza eliminar
archivos, enviar correos ni modificar repositorios sin las confirmaciones
existentes.

Referencia: https://github.com/Louis-CFM/coucou — directorios
\`windows/src-tauri/src/speech/\` y \`windows/src-tauri/src/voice/\`.

---
# HOVER — asistente personal silencioso para Windows

HOVER es una isla Windhawk con ojos y atajos. Permite usar tu voz para abrir
aplicaciones, documentos, Google Workspace y proyectos de ChatGPT/Claude.
**No habla, no emite pitidos y no necesita Codex** para sus acciones cotidianas.

## Instalar la interfaz con proyectos

1. En [GitHub, HOVER v4.5](../HOVER_v4_5_PROYECTOS_DESDE_ATAJOS_WINDHAWK.wh.cpp),
   abre el código C++.
2. En Windhawk, edita el mod existente de HOVER y reemplaza **todo su código**
   por el de v4.5. Compila con Ctrl+B y activa el mod.
3. No ejecutes dos mods HOVER a la vez. El nuevo conserva el mismo ID
   \`hover-island-v38-hardware\`, para actualizar el anterior.

**Desde la isla:** abre **Atajos** → clic izquierdo en **ChatGPT** o **Claude**.
Aparece el administrador de proyectos:
- Escribe el nombre (por ejemplo **Zap**).
- Copia la URL real del proyecto desde ChatGPT o Claude.
- Pulsa **Pegar** → **Guardar**.
- Selecciona un proyecto → **Abrir proyecto**.
- **Eliminar** borra un enlace guardado, no elimina el proyecto en la nube.
- **Abrir ChatGPT / Abrir Claude** abre el sitio general.
- **Clic derecho** sobre la tarjeta ChatGPT o Claude: abre el sitio general directamente.

La URL se guarda **localmente** en
\`%LOCALAPPDATA%\\HOVER_NEXT\\projects.tsv\`, no en GitHub.
Para ChatGPT debe ser una URL de proyecto \`https://chatgpt.com/g/g-p-...\`
y para Claude \`https://claude.ai/project/...\`.
La isla no pide contraseñas ni almacena cookies.

## Encender la voz

\`\`\`powershell
cd C:\\Users\\gomez\\hover
git pull origin main
cd .\\HOVER_NEXT
.\\INSTALAR_WINDOWS.bat
.\\PROBAR.bat
.\\INICIAR_SILENCIOSO_REALTEK.bat
\`\`\`

**Importante:** \`git pull\` actualiza los scripts y descarga el nuevo código,
pero **no reemplaza automáticamente el código que ya instalaste en Windhawk**.
El motor de voz debe quedar en ejecución y el mod de Windhawk debe estar activo
para mostrar el estado de escucha.

Se recomienda probar micrófono WASAPI **9** por ser el de este equipo,
aunque su índice puede cambiar:
\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m hover_next.app --mic-test --mic 9
\`\`\`
Si aparecen transcripciones inventadas con ruido, sube el umbral ligeramente
y asegúrate de elegir el micrófono correcto en Configuración de Windows.
La detección acústica sigue siendo experimental; las pruebas automáticas no
sustituyen probar la voz real.

## Comandos de ejemplo

- «**Hover, abre calculadora**».
- «**Hover, crea un nuevo documento de Word**» (Word instalado).
- «**Hover, abre este documento**» (seleccionado en Explorador).
- «**Hover, abre Gmail**».
- «**Hover, crea un documento de Google**».
- «**Hover, crea una hoja de cálculo**».
- «**Hover, abre ChatGPT en el proyecto Zap y escribe lo siguiente:
  revisa el planteamiento de este proyecto**».
- «**Hover, abre Claude y escríbele lo siguiente**», pausa, y dicta
  la frase siguiente.

Para ChatGPT/Claude HOVER abre un navegador de Chrome aislado: inicia
sesión allí una vez. El envío de mensajes es **experimental** y puede fallar
si cambian las interfaces de los servicios. HOVER no confirma que el
servidor recibió el mensaje, solamente que lo escribió y pulsó Enter.

Las operaciones sensibles como crear repositorios o mover archivos mantienen
una confirmación escrita. Abrir una página o aplicación no la necesita.

## Código del proyecto

- \`hover_next/wake.py\` — activación «Hover» u «Oye Hover».
- \`hover_next/voice.py\` — Whisper local, filtrado de ruido.
- \`hover_next/intent.py\`, \`direct_commands.py\`, \`chat_command.py\`
  — interpretación de comandos.
- \`hover_next/projects.py\` — enlaces compartidos con Atajos.
- \`hover_next/browser.py\` — navegador aislado para ChatGPT/Claude.
- \`hover_next/executor.py\` — acciones.
- \`hover_next/ui_bridge.py\` — estados silenciosos en la isla.
- \`tests/\` — pruebas locales y GitHub Actions.

Para detalles de funciones opcionales de programación, GitHub CLI y arquitectura
anterior, consulta [referencia técnica](REFERENCIA_TECNICA_PREVIA.md).

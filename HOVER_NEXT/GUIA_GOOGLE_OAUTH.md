# HOVER v4.6 — Google OAuth 2.0 local (Windows)

## Recuperación: OAuth JSON ausente y error WinError 5/32 en Windhawk

Si la consola dice **FALTA el archivo OAuth local**, los paquetes ya están
instalados; **no pegues "connect all" en el JSON** y no inventes
credenciales. Desde
[Google Cloud → Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients)
crea un cliente **Aplicación de escritorio**, descarga su JSON,
renómbralo \`google_oauth_client.json\` y guárdalo **fuera de GitHub** en
\`%LOCALAPPDATA%\HOVER_NEXT\google_oauth_client.json\`. Comprueba la ruta:

\`\`\`powershell
Test-Path "$env:LOCALAPPDATA\HOVER_NEXT\google_oauth_client.json"
\`\`\`

Debe imprimir \`True\`. Si imprime \`False\`, HOVER no puede iniciar OAuth;
\`connect all\` no sustituye ese archivo.

Si además aparece \`Permission denied\`, \`WinError 5\` o \`WinError 32\`
al actualizar \`voice_ui.txt\`, actualiza HOVER. El puente visual usa
archivos temporales de nombre único, reintentos limitados y avisos
reducidos, y el motor de voz limita a una sola instancia activa.
Cierra antes el HOVER anterior con Ctrl+C. Para **verificar** instancias
anteriores sin cerrar otros programas Python:

\`\`\`powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -in @("python.exe", "pythonw.exe") -and
                 $_.CommandLine -like "*hover_next.app*" } |
  Select-Object ProcessId, CommandLine
\`\`\`

Si aparece una instancia de HOVER antigua que no responde, ciérrala
desde su consola. No borres tus tokens y no elimines toda la carpeta Temp.

Después de guardar un JSON válido, ejecuta
\`INSTALAR_GOOGLE_HOVER.bat\` para comprobarlo, inicia HOVER con
\`INICIAR_HOVER.bat\` y desde **Atajos → GOOGLE** conecta primero Drive.
Autoriza en el navegador; luego conecta los demás servicios según
los necesites. La interfaz no guarda ni muestra contraseñas o tokens.

---


## Qué está implementado

- Interfaz Windhawk nueva: **Atajos → GOOGLE / Conectar cuenta**, sin quitar
  las seis tarjetas actuales. Permite conectar/desconectar **Drive, Calendar,
  Gmail y Docs** por separado o en conjunto.
- OAuth 2.0 oficial de Google para **aplicación de escritorio**. Google abre
  una página de consentimiento en el navegador. Nunca escribas tu contraseña
  dentro de HOVER ni envíes el JSON OAuth por chat/GitHub.
- Un token independiente por servicio, cifrado con **Windows DPAPI CurrentUser**
  en \`%LOCALAPPDATA%\HOVER_NEXT\google_tokens\`. Los archivos contienen datos
  binarios cifrados; no se guardan tokens en el repositorio.
- Validación de cuenta: los cuatro permisos deben pertenecer a la misma
  dirección Google; el asistente rechaza conexiones cruzadas.
- Búsqueda de documentos/archivos por metadatos en Drive, correo en Gmail,
  eventos en Calendar. Docs usa la indexación de Drive; **conecta Drive y
  Docs juntos si quieres buscar tus documentos**.
- Creación de documentos **nuevos** mediante Docs API usando el alcance
  \`drive.file\`. No modifica ni elimina documentos existentes.
- Google sigue abriendo búsquedas públicas cuando preguntas «qué», «cómo»,
  «diferencia», etc. Si tienes una cuenta conectada, también intenta buscar
  coincidencias en los servicios autorizados; **no comparte esas coincidencias
  automáticamente con ChatGPT ni Claude**.
- Para compartir resultados con una de esas cuentas debes pedirlo de manera
  explícita; se requiere confirmación para enviar metadatos privados a un
  tercero. El envío usa la sesión **Chrome independiente** ya implementada
  para ChatGPT/Claude. No comparte cookies ni autoriza esas dos cuentas vía
  OAuth de Google. El destinatario recibe título, extracto y enlace; no un
  archivo binario adjunto ni acceso automático a Drive.

## Instalación — solo una vez

**1. Crear tu propio cliente Google OAuth:** ve a
[Google Cloud Console](https://console.cloud.google.com/), crea o selecciona
un proyecto, configura la pantalla de consentimiento **Google Auth Platform**
y añade tu dirección personal como usuario de prueba si la app está en
modo *Testing*. Habilita estas APIs:

- Google Drive API
- Gmail API
- Google Calendar API
- Google Docs API

En **Clients → Create client → Desktop app** descarga el archivo JSON. Debe
tener una clave raíz \`installed\`, no \`web\`. **No subas ese archivo a
GitHub**. Cópialo a:

\`\`\`text
%LOCALAPPDATA%\HOVER_NEXT\google_oauth_client.json
\`\`\`

El archivo JSON es específico de tu proyecto Google Cloud. HOVER no incluye
credenciales ficticias ni claves de terceros.

**2. Instalar dependencias:**

\`\`\`powershell
cd C:\Users\gomez\hover
git pull origin main
cd .\HOVER_NEXT
.\INSTALAR_GOOGLE_HOVER.bat
\`\`\`

**3. Instalar el mod Windhawk v4.6.** En Windhawk edita el mod HOVER que ya
tienes, reemplaza el código completo por
[\`HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp\`](../HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp)
y compila con **Ctrl+B**. No actives dos mods HOVER. El ID del mod no cambia,
y la apariencia (ojos, panel, colores y seis tarjetas) se conserva.

**4. Iniciar la voz:**

\`\`\`powershell
.\INICIAR_HOVER.bat
\`\`\`

Abre **Atajos → GOOGLE**, pulsa **Conectar Drive** (o Conectar los cuatro) y
autoriza en tu navegador. Por cada servicio solicitado verás los permisos
antes de aceptarlos. Para operaciones de solo lectura los permisos son:

| Servicio | Scope |
|---|---|
| Drive | \`drive.metadata.readonly\` |
| Calendar | \`calendar.events.readonly\` |
| Gmail | \`gmail.readonly\` |
| Docs | \`documents.readonly\` y \`drive.file\` |
| Todos | \`userinfo.email\` para comprobar la identidad de cuenta |

**5. Desconectar:** desde Atajos → Google, pulsa Desconectar servicio o
Desconectar todos, o usa «Hover, desconecta Google». Esto elimina los
tokens cifrados locales de HOVER. Para revocar el permiso también en los
servidores de Google abre
[Mi cuenta Google → Conexiones con terceros](https://myaccount.google.com/permissions)
y revoca el acceso concedido al proyecto OAuth.

## Comandos de voz

\`\`\`text
Hover, conecta Google Drive
Hover, conecta Gmail
Hover, estado de Google
Hover, busca informe de mantenimiento en mi Drive
Hover, busca factura en mi Gmail
Hover, consulta reuniones en mi calendario
Hover, busca informes en mi cuenta de Google
Hover, crea documento de Google llamado Informe semanal
Hover, busca informe en mi Drive y envíalo a ChatGPT
Hover, busca informe en mi Drive y envíalo a Claude
Hover, qué es un PLC
Hover, busca rodamientos 6204
Hover, desconecta Google
\`\`\`

El último tipo de pregunta pública continúa mostrando Google Search. Las
búsquedas personales solo leen las APIs autorizadas. Compartir contenidos
de Google hacia una compañía de IA no se hace en segundo plano: el usuario
elige ChatGPT o Claude, confirma la salida de datos y debe haber iniciado
sesión en el Chrome controlado por HOVER.

## Privacidad y limitaciones actuales

- Google OAuth **no sustituye el inicio de sesión** de ChatGPT/Claude.
- Gmail y Drive incluyen scopes sensibles/restringidos según el tipo de
  acceso. Para publicar HOVER para otros usuarios, Google podría exigir
  verificación de la aplicación y evaluaciones adicionales.
- En modo Testing, los tokens pueden dejar de funcionar y necesitar nueva
  autorización según las políticas de Google.
- Gmail es **solo lectura**: nunca envía ni borra correos.
- Calendar es **solo lectura**: busca eventos pero no los crea ni modifica.
- Drive busca por metadatos/nombre/índice \`fullText\`, sin descargar todos los
  contenidos de Drive.
- Docs puede crear documentos nuevos y acceder a documentos autorizados;
  la búsqueda documental requiere Drive. No envía archivos adjuntos reales
  a Claude/ChatGPT: solo texto resumido (metadatos y enlaces).
- El mod Windhawk **no lee credenciales**. Escribe únicamente
  \`connect drive\`, \`disconnect gmail\`, etc. en
  \`%LOCALAPPDATA%\HOVER_NEXT\google_control.txt\`. El proceso Python
  acepta solo órdenes de una lista fija y guarda en
  \`google_status.tsv\` únicamente indicadores de conexión y un estado.
- Un vínculo sensible en un correo o documento no autoriza que HOVER lo
  abra, comparta o ejecute instrucciones encontradas en esos datos.
- Los resultados de búsqueda de tu cuenta no se sincronizan con servidores
  de HOVER; las consultas sí se envían a las APIs oficiales de Google, y
  los resultados compartidos se envían al chat que hayas indicado.
- El motor Python y el diseño de Windhawk siguen desacoplados para que
  una futura migración a una isla Windows propia conserve el mismo aspecto.

## Si el botón no responde

Comprueba que \`INICIAR_HOVER.bat\` esté funcionando. El administrador de
Google solo envía órdenes al motor Python, no inicia un servidor adicional.
El estado de conexión aparece en la ventana de Google y en el puente de
la isla.

Si la autorización falla, comprueba: JSON tipo Desktop, usuario de prueba,
APIs habilitadas, permisos aceptados y el puerto de retorno de Google OAuth
(loopback \`127.0.0.1\`). Repite solo el servicio con fallo.

**Validación:** los tests automatizados usan dobles de API y no verifican
autorización con Google real ni cuentas de ChatGPT/Claude. La compilación
de C++ se comprueba mediante MSVC sintácticamente; hace falta probar
interacción real en Windhawk y consentimiento real en Windows.

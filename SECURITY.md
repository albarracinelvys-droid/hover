# Política de seguridad de HOVER

HOVER accede a funciones del escritorio, archivos locales y, opcionalmente, cuentas autorizadas de Google. Las contribuciones y reportes de seguridad deben tratar estos componentes con especial cuidado.

## Reportar una vulnerabilidad

**No publiques credenciales, datos privados ni vulnerabilidades explotables en issues públicos.** Si GitHub ofrece la opción **Security → Report a vulnerability** para este repositorio, utiliza ese canal privado. Si no está habilitado, contacta al propietario por un canal privado antes de divulgar detalles técnicos sensibles.

Incluye una descripción del problema, el impacto y una reproducción mínima **sin datos personales**. Evita adjuntar el contenido de `%LOCALAPPDATA%\HOVER_NEXT`.

## Datos que deben permanecer fuera de Git

- `google_oauth_client.json`, `client_secret*.json` y todos los tokens OAuth.
- `config.json`, enlaces privados de proyectos y perfiles de navegador.
- Archivos de audio, transcripciones, correos, logs y documentos de usuario.
- Entornos virtuales, modelos de voz y archivos descargados.

El archivo `.gitignore` reduce commits accidentales, pero **no protege archivos que ya se versionaron**. Antes de publicar, revisa todos los commits e historial; si una clave estuvo expuesta, revócala y reemplázala incluso después de eliminar el archivo.

## Alcance y precauciones

- El reconocimiento de voz local no elimina los riesgos de órdenes mal interpretadas: confirma acciones sensibles.
- Para Google se piden permisos específicos por servicio; consulta [el detalle real de scopes](HOVER_NEXT/GUIA_GOOGLE_OAUTH.md).
- Las búsquedas y comunicaciones con ChatGPT, Claude u otros servicios externos pueden compartir el contenido solicitado con esas plataformas.
- Las validaciones de CI y los tests simulados no prueban por sí solos la seguridad en un equipo Windows real.

## Antes de compartir un diagnóstico

Sustituye nombres de usuario de Windows, correos, rutas privadas y enlaces de proyectos por ejemplos ficticios. Nunca copies tokens, códigos de autorización o archivos OAuth en un issue o pull request.

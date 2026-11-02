# HOVER

**Asistente de escritorio para Windows con una interfaz compacta en Windhawk y un motor de comandos en Python.**

HOVER permite manejar aplicaciones, archivos y búsquedas, usar comandos por voz o texto, abrir proyectos de ChatGPT/Claude y conectar opcionalmente servicios de Google mediante OAuth. Está orientado al uso personal en Windows; varias integraciones dependen de programas instalados y de autorizaciones del usuario.

> **Proyecto en desarrollo.** El reconocimiento de voz y las automatizaciones sobre interfaces de terceros pueden fallar según el micrófono, el navegador o la versión del servicio. Las pruebas automáticas no equivalen a una validación completa en Windows.

## Inicio rápido (Windows 10/11)

**Requisitos:** Git, Python 3.11 o 3.12, conexión a Internet para instalar dependencias y [Windhawk](https://windhawk.net/) para mostrar la isla. Para el reconocimiento por voz se requiere un micrófono.

En PowerShell:

```powershell
git clone https://github.com/albarracinelvys-droid/hover.git
cd hover
.\INSTALAR_HOVER.bat
.\INICIAR_HOVER.bat
```

Si ya lo habías clonado, actualiza desde la raíz:

```powershell
git pull --ff-only origin main
.\INSTALAR_HOVER.bat
.\INICIAR_HOVER.bat
```

El instalador crea `HOVER_NEXT/.venv`, instala las dependencias y el navegador Chromium requerido por Playwright. En el primer uso puede descargarse un modelo de voz. **No subas el entorno virtual ni los modelos a GitHub.**

Para detener HOVER en segundo plano:

```powershell
.\DETENER_HOVER.bat
```

Para comprobar la lógica sin micrófono, ejecuta `HOVER_NEXT\PROBAR.bat`. Para diagnosticar micrófono, usa `HOVER_NEXT\COMPROBAR_MIC_Y_ELEGIR.bat`.

## Instalar la interfaz Windhawk

1. Abre Windhawk e instala o edita un mod de usuario.
2. Copia el contenido completo de [HOVER v4.6 para Windhawk](HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp).
3. Compila el mod con **Ctrl+B** y actívalo. Mantén **un solo mod HOVER activo**.
4. Inicia el motor Python con `INICIAR_HOVER.bat`.

**Importante:** `git pull` actualiza el código local, pero **no reemplaza automáticamente** el código del mod instalado en Windhawk.

## Funciones

- Isla visual en Windhawk con accesos y estado del asistente.
- Órdenes por voz o texto para abrir aplicaciones, páginas, archivos y carpetas.
- Reconocimiento local con Whisper; Parakeet es opcional y requiere descargar su modelo.
- Accesos a proyectos ChatGPT/Claude mediante URLs guardadas localmente.
- Google Drive, Calendar, Gmail y Docs mediante permisos OAuth opcionales.
- Diagnósticos y pruebas automatizadas para componentes del motor.

Las integraciones con servicios externos pueden abrir sesiones de navegador o enviar datos a esos servicios cuando el usuario lo solicita. Revisa las confirmaciones y permisos antes de ejecutar operaciones sobre tus archivos o cuentas.

## Estructura del repositorio

| Ruta | Contenido |
| --- | --- |
| `HOVER_NEXT/hover_next/` | Motor Python actual, ejecución, voz, navegador e integraciones |
| `HOVER_NEXT/tests/` | Pruebas automatizadas |
| `HOVER_NEXT/*.bat` | Instalación, ejecución y diagnóstico en Windows |
| `HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp` | Mod Windhawk recomendado |
| `HOVER_v4_*.wh.cpp` y scripts `*_v4_*.py` | Versiones anteriores conservadas por compatibilidad |
| `.github/workflows/` | Comprobaciones automáticas |
| `docs/` | Arquitectura y guía para colaboradores |

**No se han movido ni eliminado versiones anteriores:** existen accesos directos y procedimientos de actualización que pueden depender de sus rutas.

## Google (opcional)

Los datos de inicio de sesión no vienen incluidos. Cada usuario debe crear su propio cliente OAuth de escritorio en Google Cloud y guardarlo fuera del repositorio en `%LOCALAPPDATA%\HOVER_NEXT\google_oauth_client.json`. Después:

```powershell
.\HOVER_NEXT\INSTALAR_GOOGLE_HOVER.bat
```

Consulta la [guía OAuth](HOVER_NEXT/GUIA_GOOGLE_OAUTH.md) para los **permisos reales solicitados**, entre ellos acceso de lectura a Gmail, creación de borradores y creación de eventos en Calendar. Autoriza únicamente los servicios que quieras usar.

**Nunca compartas** archivos OAuth reales, tokens, perfiles de navegador, registros con contenido privado ni configuraciones personales. Revisa la [política de seguridad](SECURITY.md).

## Documentación y colaboración

- [Guía del motor HOVER NEXT](HOVER_NEXT/README.md)
- [Comandos de uso habitual](HOVER_NEXT/COMANDOS_RAPIDOS.md)
- [Uso sencillo](HOVER_NEXT/USO_SIMPLE.md)
- [Arquitectura y versiones](docs/ARQUITECTURA.md)
- [Cómo contribuir](CONTRIBUTING.md)
- [Reportar vulnerabilidades](SECURITY.md)

### Pruebas para desarrolladores

En un entorno con las dependencias necesarias, desde `HOVER_NEXT/`:

```powershell
python -m compileall -q hover_next tests
python -m unittest discover -s tests -v
```

GitHub Actions ejecuta las pruebas de Python y una comprobación de compilación del código C++ de Windhawk. Los modelos de voz, OAuth real y dispositivos de Windows necesitan pruebas manuales.

## Licencia

El repositorio es **público**, pero todavía **no contiene una licencia de reutilización**. La visibilidad pública no otorga automáticamente permiso para redistribuir o modificar el código. Antes de aceptar contribuciones o distribuir versiones, el propietario debe elegir una licencia adecuada.

## Rendimiento y perfiles de voz

Si HOVER tarda varios segundos en responder, desde la carpeta raíz utiliza
`INICIAR_HOVER_RAPIDO.bat`. Este archivo detiene con seguridad la instancia
anterior de HOVER y reinicia con un perfil más liviano: Whisper **base**,
beam **2**, pausa de escucha de **600 ms** y espera máxima de **6 s** para
el modelo semántico opcional. Si el motor Parakeet está instalado,
HOVER lo sigue prefiriendo automáticamente.

```powershell
git pull --ff-only origin main
.\INICIAR_HOVER_RAPIDO.bat
```

Para priorizar la precisión del reconocimiento, en la misma consola puedes
usar `HOVER_WHISPER_MODEL=small` y `HOVER_WHISPER_BEAM=5`
(consulta `docs/RENDIMIENTO.md`). El modo normal mantiene una
pausa de 750 ms para no separar frases largas; en el modo rápido,
una pausa de 600 ms podría dividir algunas instrucciones.

Para verificar dónde se consume el tiempo, consulta únicamente las métricas
del registro local con `DIAGNOSTICAR_RENDIMIENTO_HOVER.bat`.
No compartas registros completos sin eliminar datos personales.

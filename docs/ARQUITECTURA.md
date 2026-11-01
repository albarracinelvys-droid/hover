# Arquitectura y mapa del repositorio HOVER

## Componentes principales

```text
HOVER (Windows)
├── Windhawk: HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp
│   └── Isla visual, atajos, estados y acciones de interfaz
└── HOVER_NEXT/
    ├── hover_next/
    │   ├── app.py / launch_background.py   Entrada y ejecución
    │   ├── wake.py / voice*.py / audio*.py  Voz y activación
    │   ├── intent.py / local_nlu.py         Interpretación de órdenes
    │   ├── executor.py / pc_files.py        Acciones locales
    │   ├── browser.py / projects.py         Navegador y proyectos
    │   ├── google_*.py                      Google OAuth y APIs
    │   └── ui_bridge.py                     Estado de la isla
    ├── tests/                               Pruebas
    ├── requirements*.txt                    Dependencias
    └── *.bat                                Instalación y herramientas
```

El código Windhawk y el motor Python son **dos componentes que se actualizan por separado**. Un `git pull` no actualiza el mod ya compilado en Windhawk.

## Qué versión utilizar

- **Actual:** `HOVER_NEXT/` para el motor Python y `HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp` para Windhawk.
- **Históricas:** `HOVER_v4_1_...`, `HOVER_v4_2_...`, `HOVER_v4_5_...`, `Asistente_Voz_HOVER_v4_*.py` y utilidades anteriores siguen en la raíz para no romper instalaciones existentes.
- **Compatibilidad:** los cambios de estructura futuros deberían migrar primero los scripts que hacen referencia a rutas antiguas y aportar una vía de actualización.

## Datos y seguridad

La aplicación guarda su estado por usuario bajo `%LOCALAPPDATA%\HOVER_NEXT`, en lugar del repositorio, incluidas configuraciones y credenciales de Google. Los tokens OAuth se almacenan cifrados en Windows DPAPI según la implementación actual. No copies esa carpeta al árbol Git.

Google OAuth es opcional. Drive usa metadatos de solo lectura; Calendar permite leer y crear eventos; Gmail permite leer y crear borradores, **sin enviar correos** desde la función de borrador; Docs permite leer y crear documentos según los permisos indicados en la [guía OAuth](../HOVER_NEXT/GUIA_GOOGLE_OAUTH.md).

## Estado de las pruebas

El workflow Python corre en Ubuntu con Python 3.11 y 3.12. El workflow C++ compila una unidad de traducción con un stub de Windhawk en Windows. Ninguno sustituye las pruebas con una instalación real de Windhawk, micrófono, cuentas OAuth o modelos de voz descargados.

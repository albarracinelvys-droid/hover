# Contribuir a HOVER

Gracias por ayudar a mejorar HOVER. El proyecto combina un motor Python y una interfaz Windhawk en C++, por lo que los cambios deben priorizar **compatibilidad con Windows, privacidad y seguridad de las acciones automatizadas**.

## Antes de proponer cambios

1. Revisa el [README principal](README.md) y la [arquitectura](docs/ARQUITECTURA.md).
2. Abre un issue con la versión de Windows, Python, Windhawk, el comportamiento esperado y los pasos para reproducir el fallo.
3. Elimina de los registros cualquier correo, token, ruta personal, nombre de archivo sensible o contenido de conversaciones.
4. Trabaja en una rama separada y crea un pull request pequeño con descripción y forma de verificación.

## Pruebas

Desde `HOVER_NEXT/`, con Python 3.11 o 3.12 y las dependencias de prueba instaladas:

```powershell
python -m compileall -q hover_next tests
python -m unittest discover -s tests -v
```

Para cambios en la interfaz, prueba también la compilación en Windhawk, la interacción con el motor de voz y el cierre sin dejar procesos huérfanos. En los PR indica explícitamente qué **no** pudiste comprobar.

## Reglas importantes

- No incluir credenciales OAuth, contraseñas, tokens, modelos descargados ni datos privados.
- No registrar ni publicar transcripciones, correos o archivos personales sin anonimizar.
- Mantener confirmaciones para operaciones sensibles y no introducir ejecución arbitraria de comandos.
- No cambiar las rutas de scripts existentes o archivos de versiones previas sin un plan de compatibilidad.
- Agregar pruebas para correcciones funcionales siempre que sea posible.
- No afirmar que una integración externa funciona en producción solo por superar tests simulados.

## Licencia

El proyecto aún no tiene archivo `LICENSE`. Una contribución no implica que el código esté disponible bajo una licencia de código abierto. El propietario debe definir primero las condiciones de licencia y contribución.

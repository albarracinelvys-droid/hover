# Ojos reactivos de HOVER

La interfaz v4.6 anima los estados reales que publica el motor Python: listening (atención y dilatación suave), thinking (mirada de búsqueda), ok (asentimiento y guiño breve), error (sacudida breve). Las expresiones regresan gradualmente al reposo. La mirada y las transiciones utilizan el tiempo entre cuadros; los iris quedan recortados dentro de cada ojo durante el parpadeo.

## Aplicar

1. Ejecuta `git pull --ff-only origin main` dentro del repositorio.
2. Abre `HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp` y copia todo el contenido.
3. En Windhawk, edita el mod HOVER existente, reemplaza el código, compila con Ctrl+B y actívalo.
4. Inicia `HOVER_NEXT/INICIAR_HOVER.bat`.

Actualizar Git no reemplaza el código instalado en Windhawk. No actives dos mods HOVER a la vez.

## Comprobación

Di «Oye Hover», luego una orden. La mirada atenta debe cambiar al procesamiento y al gesto de éxito cuando el motor informe el resultado. Los errores informados por el motor generan una sacudida breve. La isla conserva su tamaño y navegación manual.

Se comprobaron las curvas numéricas a 30, 60 y 120 Hz y los límites de altura del parpadeo. La compilación GDI+/Windhawk y la revisión visual deben realizarse en Windows; no se verificaron en el entorno Linux.

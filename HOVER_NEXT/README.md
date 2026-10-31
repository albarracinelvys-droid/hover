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

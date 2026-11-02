# Diagnóstico y optimización de latencia en HOVER

HOVER funciona en Windows con transcripción local. La velocidad depende de la
CPU, memoria, micrófono y del motor instalado: Parakeet o Whisper. No existe
una medición universal válida para todos los equipos.

## Perfil rápido

Ejecuta `INICIAR_HOVER_RAPIDO.bat` desde la raíz. El script termina la
instancia anterior de HOVER (sin afectar otros procesos Python) e inicia:
- Whisper `base` en CPU, `beam_size=2` si no hay Parakeet.
- Pausa de VAD de 600 ms (el normal mantiene 750 ms).
- Límite de 6 segundos al modelo Qwen opcional.

No instala modelos ni conecta servicios externos nuevos. En el primer
arranque, faster-whisper puede descargar el modelo base.

## Perfil de máxima precisión

Desde PowerShell, en la raíz de HOVER:

```powershell
.\DETENER_HOVER.bat
$env:HOVER_WHISPER_MODEL = "small"
$env:HOVER_WHISPER_BEAM = "5"
$env:HOVER_NLU_TIMEOUT = "15"
$env:HOVER_VAD_PAUSE_MS = "750"
.\INICIAR_HOVER.bat
```

Las opciones se heredan por el proceso de voz al iniciarlo y no afectan
la configuración de otros programas. Para volver al perfil rápido, ejecuta
`INICIAR_HOVER_RAPIDO.bat`.

## Diagnóstico de la demora

Usa `DIAGNOSTICAR_RENDIMIENTO_HOVER.bat` para mostrar las últimas métricas
sin imprimir transcripciones, nombres de archivo ni contenidos de Google.

- `[latencia] cola=`: tiempo esperando al reconocimiento.
- `asr=`: transcripción local.
- `entrega_accion=`: tiempo para dejar la transcripción en cola.
- `cola_accion=`: espera antes de interpretar y ejecutar.
- `interpretacion_y_accion=`: tiempo de análisis semántico y ejecución.
- `[latencia] modelo_local=`: tiempo consumido por Qwen vía Ollama.

Si `asr` es alto, prueba el perfil rápido o Parakeet.
Si `modelo_local` es alto, puedes reducir `HOVER_NLU_TIMEOUT` o desactivar
temporalmente la interpretación semántica con `HOVER_NLU=off` (algunas frases
flexibles dejarán de reconocerse). Si `interpretacion_y_accion` es alto,
separa el problema entre el navegador, la aplicación o un servicio externo;
esas operaciones no deben detener el hilo de reconocimiento.

No publiques el archivo `voice.log` completo porque puede incluir frases
dictadas, información de proyectos y nombres de archivos.

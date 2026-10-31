"""Whisper local voice listener with explicit wake phrase.

The recognizer captures five-second audio windows. This is a test harness,
not a continuous low-latency hotword engine, and cannot identify a speaker.
"""
from __future__ import annotations

import time

import numpy as np

from .app import run_one
from .wake import extract_wake


def _wake_feedback():
    # This is only audio feedback, not synthesized voice or authentication.
    try:
        import winsound
        winsound.Beep(880, 120)
    except (ImportError, RuntimeError, OSError):
        pass


def run_voice(executor, model_name="small"):
    import sounddevice as sd
    from faster_whisper import WhisperModel

    print("Cargando Whisper local:", model_name, flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    sr = 16000
    awaiting = False
    wake_deadline = 0.0
    try:
        print("Micrófono:", sd.query_devices(kind="input")["name"])
    except Exception as exc:
        print("No se pudo consultar el micrófono predeterminado:", exc)
    print("Di: Oye Hover. Ctrl+C para detener. El audio se transcribe localmente.")
    print("Nota: cada bloque de escucha tarda 5 segundos más el procesamiento de Whisper.")

    try:
        while True:
            audio = sd.rec(int(5.0 * sr), samplerate=sr, channels=1, dtype="float32")
            sd.wait()
            samples = np.asarray(audio, dtype=np.float32).reshape(-1)
            if float(np.sqrt(np.mean(samples * samples))) < 0.005:
                continue

            segments, _ = model.transcribe(
                samples, language="es", beam_size=5, vad_filter=True,
                condition_on_previous_text=False,
            )
            spoken = " ".join(s.text.strip() for s in segments).strip()
            if not spoken:
                continue

            print("Reconocido:", spoken)
            command = extract_wake(spoken)

            if command is not None:
                _wake_feedback()
                if not command:
                    awaiting = True
                    wake_deadline = time.monotonic() + 12.0
                    print("[listening] Oye Hover detectado. Te escucho.")
                    continue
                awaiting = False
                print("[wake] Activacion reconocida. Orden:", command)
                run_one(command, executor)
            elif awaiting and time.monotonic() <= wake_deadline:
                awaiting = False
                print("[wake] Orden posterior:", spoken)
                run_one(spoken, executor)
            else:
                awaiting = False
                print("[idle] No se detecto 'Oye Hover' al inicio; no se ejecuto nada.")
    except KeyboardInterrupt:
        print("HOVER detenido.")

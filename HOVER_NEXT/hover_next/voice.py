"""Whisper local listener with real-time microphone diagnostics."""
from __future__ import annotations
import time

from .app import run_one
from .wake import extract_wake
from .audio import microphone_events


def _wake_feedback():
    try:
        import winsound
        winsound.Beep(880, 120)
    except (ImportError, RuntimeError, OSError):
        pass


def test_microphone(device=None, threshold: float = 0.0008, duration: float = 15):
    print("[diagnóstico] Habla cerca del micrófono; verás el RMS sin iniciar Whisper.")
    try:
        for _kind, _payload in microphone_events(
                device=device, threshold=threshold, diagnostic=True, duration=duration):
            pass
    except KeyboardInterrupt:
        print("[diagnóstico] Detenido.")
    except Exception as exc:
        print(f"[ERROR micrófono] {type(exc).__name__}: {exc}")
        raise
    print("[diagnóstico] Finalizado.")


def run_voice(executor, model_name="small", device=None, threshold: float = 0.0008):
    from faster_whisper import WhisperModel

    print("[asr] Cargando Whisper local:", model_name, flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print("[ready] Whisper preparado. Escucha por actividad de voz.", flush=True)
    print("Di: 'Oye Hover' o 'Oye Hover, abre ChatGPT'. Ctrl+C para detener.", flush=True)
    print("Si nunca aparece '[asr] Voz detectada', ejecuta --mic-test.", flush=True)
    awaiting = False
    wake_deadline = 0.0

    try:
        for event, audio in microphone_events(device=device, threshold=threshold):
            if event != "segment":
                continue
            segments, _ = model.transcribe(
                audio, language="es", beam_size=5, vad_filter=True,
                condition_on_previous_text=False,
            )
            spoken = " ".join(s.text.strip() for s in segments).strip()
            if not spoken:
                print("[asr] No hubo palabras suficientemente claras.", flush=True)
                continue

            print("Reconocido:", spoken, flush=True)
            command = extract_wake(spoken)
            if command is not None:
                _wake_feedback()
                if not command:
                    awaiting = True
                    wake_deadline = time.monotonic() + 15.0
                    print("[listening] Oye Hover detectado. Te escucho.", flush=True)
                    continue
                awaiting = False
                print("[wake] Orden:", command, flush=True)
                run_one(command, executor)
            elif awaiting and time.monotonic() <= wake_deadline:
                awaiting = False
                print("[wake] Orden posterior:", spoken, flush=True)
                run_one(spoken, executor)
            else:
                awaiting = False
                print("[idle] No se detectó 'Oye Hover' al principio de la frase.", flush=True)
    except KeyboardInterrupt:
        print("HOVER detenido.")
    except Exception as exc:
        print(f"[ERROR voz] {type(exc).__name__}: {exc}", flush=True)
        raise

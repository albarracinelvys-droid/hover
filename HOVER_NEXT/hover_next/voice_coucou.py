"""HOVER voice engine v5: Coucou-style adaptive speech detection and local STT.

Microphone capture never waits for recognition: streaming audio and ASR run in
separate threads. Supports "Hover, abre calculadora", "Oye Hover", and F8
(push-to-command fallback). No synthesized speech, no alert sounds.
"""
from __future__ import annotations

from queue import Empty, Full, Queue
import threading
import time

import numpy as np

from .audio_coucou import AdaptiveVad, FRAME, resample_frame, normalize_audio
from .intent import Intent, parse
from .wake import extract_wake
from .ui_bridge import publish
from .recognizers import create_recognizer


class VoiceDialogue:
    """Text-only state transitions; testing this doesn't require a microphone."""
    def __init__(self, execute, send_dictated, clock=time.monotonic):
        self.execute = execute
        self.send_dictated = send_dictated
        self.clock = clock
        self.command_until = 0.0
        self.ptt_until = 0.0
        self.dictation_provider = ""
        self.dictation_until = 0.0

    def press_hotkey(self):
        self.ptt_until = self.clock() + 10.0
        publish("listening", "Comando por F8")
        print("[F8] Di ahora tu orden, sin decir Hover.",flush=True)

    def process(self, spoken: str):
        spoken = spoken.strip()
        if not spoken:
            return "silence"
        now = self.clock()
        print("[voz]",spoken,flush=True)

        # Any new explicit wake phrase can override an unfinished dictation.
        remainder = extract_wake(spoken)
        if remainder is not None:
            self.dictation_provider = ""
            self.ptt_until = 0
            if not remainder:
                self.command_until = now + 12.0
                publish("listening", "Te escucho")
                print("[wake] HOVER detectado. Di tu orden.",flush=True)
                return "wake"
            self.command_until = 0.0
            return self._command(remainder)

        if self.dictation_provider and now < self.dictation_until:
            provider = self.dictation_provider
            self.dictation_provider = ""
            if spoken.casefold().strip(" .!?") in ("cancela","cancelar","no enviar"):
                publish("ok", "Dictado cancelado")
                return "cancel"
            return self.send_dictated(provider,spoken)

        if now < self.command_until or now < self.ptt_until:
            from .wake import normalize_speech
            filler = normalize_speech(spoken)
            if filler in ("oye", "hey", "si", "ok", "hola", "hover"):
                # A filler is not a complete command. Remain ready for the next phrase.
                self.command_until = max(self.command_until, now + 8.0)
                print("[listening] Espero la orden completa.",flush=True)
                return "waiting"
            self.command_until = self.ptt_until = 0.0
            return self._command(spoken)

        print("[idle] No se reconocio el nombre Hover. Prueba F8.",flush=True)
        return "ignored"

    def _command(self, utterance):
        command = parse(utterance)
        if command.action == "unknown":
            publish("error", "Orden no reconocida: "+utterance[:50])
            print("[accion] Sin coincidencia:",utterance,flush=True)
            return "unknown"
        print("[accion]",command.action,command.args,flush=True)
        result = self.execute(utterance)
        if result is not None and command.action == "chat_prepare":
            self.dictation_provider = command.provider
            self.dictation_until = self.clock()+65.0
            publish("listening","Dicta tu mensaje para "+command.provider)
            print("[dictado] Di tu mensaje ahora; no necesitas Hover.",flush=True)
        return "action" if result is not None else "failed"


def mic_test(device=None, threshold=0.0008, seconds=12.0):
    from .voice import test_microphone
    return test_microphone(device=device,threshold=threshold)


def _hotkey_pressed():
    # No keyboard hooks; a harmless poll for F8 on Windows.
    import sys
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)
    except Exception:
        return False


def run(executor, *, engine="auto", model="small",
        device=None, threshold=0.0008):
    import sounddevice as sd
    from .app import run_one

    publish("thinking","Cargando motor local")
    recognizer = create_recognizer(engine, model)
    info = sd.query_devices(device,kind="input")
    sample_rate = int(round(info["default_samplerate"]))
    if sample_rate <= 0:
        sample_rate=48000
    input_frames = int(round(sample_rate*0.03))
    audio_queue = Queue(maxsize=180)
    work_queue = Queue(maxsize=4)
    vad = AdaptiveVad(minimum_rms=threshold)
    stop = threading.Event()
    error = []

    def send_dictated(provider,spoken):
        print("[dictado]",provider,spoken,flush=True)
        try:
            publish("thinking","Enviando mensaje a "+provider)
            result = executor.execute(
                Intent("chat_send_prepared",provider=provider,
                       args={"prompt":spoken}),confirmed=True
            )
            publish("ok",str(result),3)
            print("[ok]",result,flush=True)
            return "action"
        except Exception as exc:
            publish("error",str(exc))
            print("[error]",type(exc).__name__,str(exc),flush=True)
            return "failed"

    dialogue = VoiceDialogue(lambda command:run_one(command,executor),send_dictated)

    def recognizer_worker():
        try:
            while not stop.is_set() or not work_queue.empty():
                try:
                    samples = work_queue.get(timeout=0.2)
                except Empty:
                    continue
                print(f"[asr] Transcribiendo {len(samples)/16000:.1f}s con {recognizer.name}",flush=True)
                try:
                    text = recognizer.transcribe(normalize_audio(samples))
                    if text:
                        # Reject characteristic Whisper silence hallucinations.
                        noisy_phrases=("subtitulos realizados","subtitulos por la comunidad",
                                       "hasta la proxima","suscribete","amara.org")
                        from .wake import normalize_speech
                        cleaned = normalize_speech(text)
                        if any(phrase in cleaned for phrase in noisy_phrases):
                            print("[asr] Fragmento descartado por ruido.",flush=True)
                        else:
                            dialogue.process(text)
                    else:
                        print("[asr] No hubo palabras claras. Intenta hablar mas cerca.",flush=True)
                except Exception as exc:
                    print("[asr] Error:",type(exc).__name__,exc,flush=True)
                    publish("error",str(exc))
                finally:
                    work_queue.task_done()
        except Exception as exc:
            error.append(exc)
            stop.set()

    def callback(indata, frame_count, ti, status):
        if status:
            print("[mic] Aviso del controlador:",status,flush=True)
        try:
            audio_queue.put_nowait(indata[:,0].copy())
        except Full:
            try:audio_queue.get_nowait()
            except Empty:pass
            try:audio_queue.put_nowait(indata[:,0].copy())
            except Full:pass

    worker=threading.Thread(target=recognizer_worker,name="HOVER-LocalASR",daemon=True)
    worker.start()
    publish("idle","HOVER listo")
    print(f"[ready] HOVER v5 | {recognizer.name} | {info['name']} | "
          f"dispositivo={device if device is not None else 'predeterminado'} "
          f"| {sample_rate} Hz",flush=True)
    print("[ready] Di 'Hover, abre calculadora' o pulsa F8 y di 'abre calculadora'. "
          "Sin voz, sin pitidos.",flush=True)
    print("[ready] El reconocimiento transcurre en paralelo al microfono.",flush=True)
    last_meter=time.monotonic()
    f8_was_down=False
    try:
        with sd.InputStream(samplerate=sample_rate,device=device,channels=1,
                            blocksize=input_frames,dtype="float32",callback=callback):
            while not stop.is_set():
                f8_down=_hotkey_pressed()
                if f8_down and not f8_was_down:
                    dialogue.press_hotkey()
                f8_was_down=f8_down
                try:
                    raw=audio_queue.get(timeout=0.08)
                except Empty:
                    if error:break
                    continue
                frame=resample_frame(raw,FRAME)
                segment=vad.feed(frame)
                now=time.monotonic()
                if now-last_meter>=5.0:
                    print(f"[mic] RMS={vad.rms:.5f} "
                          f"umbral_adaptativo={vad.threshold:.5f} "
                          f"voz={'si' if vad.active else 'no'} "
                          f"cola={work_queue.qsize()}",flush=True)
                    last_meter=now
                if segment is not None:
                    try:
                        work_queue.put_nowait(segment)
                    except Full:
                        print("[asr] Cola llena, se descarto un segmento antiguo.",flush=True)
    except KeyboardInterrupt:
        print("[idle] HOVER detenido por el usuario.",flush=True)
    finally:
        stop.set()
        worker.join(timeout=2.0)
        publish("idle","")
    if error:
        raise RuntimeError("El reconocedor se detuvo: "+str(error[0]))

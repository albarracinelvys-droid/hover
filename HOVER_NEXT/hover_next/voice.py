"""Silent Whisper listener; wake phrase triggers UI status, never speech output.

Short microphone blocks are measured continuously. A simple energy detector
segments utterances so silence does not hide behind a fixed five-second gate.
"""
from __future__ import annotations

import time
from collections import deque

from .app import run_one
from .intent import Intent, parse
from .wake import extract_wake
from .ui_bridge import publish


def _microphone(device, threshold, diagnostic, on_utterance=None, seconds=None):
    import sounddevice as sd
    import numpy as np

    info=sd.query_devices(device,kind="input")
    rate=int(round(info["default_samplerate"])) or 48000
    block=max(1,round(rate*0.03))
    pre=deque(maxlen=15)
    quiet=0
    onset=0
    frames=[]
    active=False
    voiced_frames=0
    started=time.monotonic()
    last_print=0.0
    print(f"[mic] {info['name']} | dispositivo={device if device is not None else 'predeterminado'} | {rate} Hz",flush=True)
    print(f"[mic] Umbral RMS={threshold:.5f}. Sin voz sintetizada.",flush=True)
    with sd.InputStream(device=device,samplerate=rate,channels=1,dtype="float32",
                        blocksize=block) as stream:
        while seconds is None or time.monotonic()-started < seconds:
            raw,overflow=stream.read(block)
            samples=raw.reshape(-1).copy()
            rms=float(np.sqrt(np.mean(samples*samples)))
            speech=rms >= threshold
            now=time.monotonic()
            if now-last_print >= (0.5 if diagnostic else 2.0):
                print(f"[mic] RMS={rms:.5f} umbral={threshold:.5f} hablando={'si' if active else 'no'}"
                      +(" [desbordamiento]" if overflow else ""),flush=True)
                last_print=now
            if diagnostic:continue
            if not active:
                pre.append(samples)
                onset=(onset+1) if speech else 0
                if onset >= 6:
                    active=True;quiet=0
                    voiced_frames=onset
                    frames=list(pre);pre.clear()
                continue
            frames.append(samples)
            quiet=0 if speech else quiet+1
            if speech:
                voiced_frames+=1
            if quiet>=23 or len(frames)>=400:
                audio=np.concatenate(frames)
                enough_speech=voiced_frames>=12
                active=False;frames=[];pre.clear();quiet=0;onset=0;voiced_frames=0
                # Ignore impulsive sound and microphone artifacts: 12 active
                # 30ms blocks (~360ms) of actual audio are required.
                if not enough_speech or len(audio) < int(rate*0.40):
                    continue
                # Whisper requires 16 kHz; resample from the driver's native rate.
                if rate!=16000:
                    target=max(1,round(len(audio)*16000/rate))
                    audio=np.interp(np.linspace(0,len(audio)-1,target),
                                    np.arange(len(audio)),audio).astype("float32")
                print(f"[asr] Voz detectada ({len(audio)/16000:.1f}s); transcribiendo...",flush=True)
                on_utterance(audio)


def test_microphone(device=None,threshold=0.0008):
    print("Diagnostico: habla normalmente durante 15 segundos.")
    _microphone(device,threshold,True,seconds=15.0)
    print("Diagnostico terminado.")


def run_voice(executor,model_name="small",device=None,threshold=0.0008):
    from faster_whisper import WhisperModel
    if not (0 < threshold < 1):
        raise ValueError("threshold debe ser mayor a cero y menor a uno")
    print("[asr] Cargando Whisper local",model_name,flush=True)
    model=WhisperModel(model_name,device="cpu",compute_type="int8")
    awaiting=False
    deadline=0.0
    chat_provider=None
    chat_deadline=0.0
    print("[ready] HOVER esta escuchando. No utilizara voz sintetizada ni pitidos.",flush=True)
    publish("idle","Oye Hover para dar una orden")

    def execute_voice_command(command):
        nonlocal chat_provider, chat_deadline
        interpreted=parse(command)
        result=run_one(command,executor)
        if interpreted.action=="chat_prepare" and result is not None:
            chat_provider=interpreted.provider
            chat_deadline=time.monotonic()+60.0
            publish("listening","Dicta el mensaje para "+chat_provider)
            print("[dictado] Di ahora el texto que quieres enviar.",flush=True)
        else:
            chat_provider=None
        return result

    def heard(audio):
        nonlocal awaiting,deadline,chat_provider,chat_deadline
        segments,_=model.transcribe(audio,language="es",beam_size=5,
                                    vad_filter=True,condition_on_previous_text=False,
                                    no_speech_threshold=0.65)
        # A short noisy segment may cause Whisper to invent generic phrases.
        # Skip low-confidence transcriptions rather than adding them as aliases.
        confident=[seg.text.strip() for seg in segments
                   if seg.avg_logprob > -1.0 and seg.no_speech_prob < 0.70]
        spoken=" ".join(confident).strip()
        if not spoken:
            print("[asr] No se reconocieron palabras",flush=True)
            return
        print("Reconocido:",spoken,flush=True)
        command=extract_wake(spoken)
        if command is not None:
            if not command:
                awaiting=True;deadline=time.monotonic()+14.0
                print("[listening] HOVER detectado. Di tu orden.",flush=True)
                publish("listening","Te escucho")
                return
            awaiting=False
            execute_voice_command(command)
        elif chat_provider and time.monotonic()<=chat_deadline:
            provider=chat_provider
            chat_provider=None
            if spoken.casefold().strip(" !?.") in ("cancelar","cancela","no enviar"):
                publish("ok","Dictado cancelado")
                print("[dictado] Cancelado.",flush=True)
                return
            print("[dictado] Mensaje para",provider,":",spoken,flush=True)
            publish("thinking","Enviando mensaje a "+provider)
            try:
                result=executor.execute(
                    Intent("chat_send_prepared",provider=provider,args={"prompt":spoken}),confirmed=True
                )
                publish("ok",str(result),3)
                print("[ok]",result,flush=True)
            except Exception as exc:
                publish("error",str(exc))
                print("[error]",type(exc).__name__,str(exc),flush=True)
        elif awaiting and time.monotonic()<=deadline:
            awaiting=False
            execute_voice_command(spoken)
        else:
            awaiting=False
            chat_provider=None
            print("[idle] Frase sin activacion; ignorada",flush=True)

    try:
        _microphone(device,threshold,False,on_utterance=heard)
    except KeyboardInterrupt:
        print("HOVER detenido.")
    finally:
        publish("idle","")

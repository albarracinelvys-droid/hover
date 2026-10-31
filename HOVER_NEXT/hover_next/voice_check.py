"""One-time live microphone comparison. No recordings are saved or uploaded.

Read aloud 'Hover abre calculadora' after each prompt. Reports the actual
recognized words and stores only the chosen PortAudio device index.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
import numpy as np

from .audio_coucou import normalize_audio
from .executor import app_dir
from .recognizers import create_recognizer
from .intent import parse
from .wake import extract_wake, normalize_speech


def recognition_score(transcript):
    text=normalize_speech(transcript)
    if parse(transcript).action == "windows_app":
        return 1.0
    if not text:
        return 0.0
    target="hover abre calculadora"
    similarity=SequenceMatcher(None,text,target).ratio()
    if extract_wake(transcript) is not None:
        similarity = max(similarity,0.7)
    return round(similarity,3)


def capture_test(device: int, recognizer) -> tuple[float,str]:
    import sounddevice as sd
    info=sd.query_devices(device,kind="input")
    rate=int(round(info["default_samplerate"]))
    print(f"\n[prueba] Microfono {device}: {info['name']}",flush=True)
    input("Pulsa Enter y di claramente: HOVER ABRE CALCULADORA. Tienes 5 segundos...")
    print("[mic] Grabando SOLO en memoria 5 segundos...",flush=True)
    data=sd.rec(rate*5,samplerate=rate,channels=1,device=device,dtype="float32")
    sd.wait()
    audio=data[:,0].copy()
    rms=float(np.sqrt(np.mean(audio*audio)))
    # Convert complete five-second phrase to 16k, avoiding VAD in this test.
    if rate!=16000:
        new_length=int(len(audio)*16000/rate)
        audio=np.interp(np.linspace(0,len(audio)-1,new_length),
                        np.arange(len(audio)),audio).astype(np.float32)
    text=recognizer.transcribe(normalize_audio(audio))
    score=recognition_score(text)
    print(f"[resultado] Nivel RMS={rms:.5f} | Transcripcion: {text!r} "
          f"| Coincidencia: {score:.0%}",flush=True)
    return score,text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--engine",choices=("auto","whisper","parakeet"),default="auto")
    parser.add_argument("--devices",default="1,9")
    args=parser.parse_args()
    recognizer=create_recognizer(args.engine)
    choices=[]
    for value in args.devices.split(","):
        try:
            device=int(value.strip())
            score,text=capture_test(device,recognizer)
            choices.append((score,device,text))
        except Exception as exc:
            print(f"[mic] Dispositivo {value}: {type(exc).__name__}: {exc}",flush=True)
    if not choices:
        raise RuntimeError("No pude abrir ningun microfono.")
    score,device,text=max(choices,key=lambda x:x[0])
    if score<0.50:
        print("[ATENCION] Ningun microfono reconocio bien la frase. "
              "Revisa permisos y seleccion de entrada en Windows. "
              "No voy a elegir uno al azar.",flush=True)
        return
    path=app_dir()/"config.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    config=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    config["preferred_mic"]=device
    target=path.with_suffix(".tmp")
    target.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    target.replace(path)
    print(f"[OK] HOVER usara el microfono {device}. Configuracion guardada LOCALMENTE.",flush=True)
    print("[OK] Ya puedes ejecutar INICIAR_HOVER.bat.",flush=True)

if __name__=="__main__":
    main()

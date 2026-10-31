"""Whisper local voice loop. Speech is processed on-device, with wake-word gating.
Speech recognition is NOT a secure authentication factor.
"""
from __future__ import annotations
import re
import time
import numpy as np
from .app import run_one
from .intent import normalize

WAKE=re.compile(r'^(?:oye|hey|hola)\s+(?:hover|jover|over|llover)\b[,.: ]*')

def run_voice(executor,model_name='small'):
    import sounddevice as sd
    from faster_whisper import WhisperModel
    print('Cargando Whisper local:',model_name)
    model=WhisperModel(model_name,device='cpu',compute_type='int8')
    sr=16000;awaiting=False;wake_deadline=0.0
    print('Di: Oye Hover. Ctrl+C para detener. Se escucha solo mientras se ejecuta el proceso.')
    try:
        while True:
            # Simple bounded capture; a production release should use audio VAD and hotword detector.
            audio=sd.rec(int(5.0*sr),samplerate=sr,channels=1,dtype='float32')
            sd.wait()
            samples=np.asarray(audio,dtype=np.float32).reshape(-1)
            if float(np.sqrt(np.mean(samples*samples)))<0.005:continue
            segments,_=model.transcribe(samples,language='es',beam_size=5,vad_filter=True,
                                        condition_on_previous_text=False)
            spoken=' '.join(s.text.strip() for s in segments).strip()
            if not spoken:continue
            print('Reconocido:',spoken)
            n=normalize(spoken)
            match=WAKE.match(n)
            if match:
                n=n[match.end():].strip()
                if not n:
                    awaiting=True;wake_deadline=time.monotonic()+10.0
                    print('HOVER: Te escucho.')
                    continue
                awaiting=False
                run_one(n,executor)
            elif awaiting and time.monotonic()<=wake_deadline:
                awaiting=False
                run_one(n,executor)
            else:
                awaiting=False
    except KeyboardInterrupt:print('HOVER detenido.')

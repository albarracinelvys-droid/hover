"""Local speech backends.

Parakeet uses the same family/model as Coucou Windows via sherpa-onnx.
Whisper is kept for computers without the optional 670 MB Parakeet download.
No recording is saved. All recognition is local after model installation.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .executor import app_dir

MODEL_REPO = "csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
# Pinned model commit used by Coucou Windows.
MODEL_REVISION = "2bda32ec70b097a55adaa07d9a7173915b43cc78"
FILES = {
    "encoder.int8.onnx": ("acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247", 652184281),
    "decoder.int8.onnx": ("179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e", 11845275),
    "joiner.int8.onnx": ("3164c13fc282100944d20fcb5fdc78bff28b4db2f8d0b329101719c0948b3", 6355277),
    "tokens.txt": ("d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d", 93939),
}
MODEL_DIR = app_dir() / "models" / "parakeet"


def has_parakeet() -> bool:
    return all((MODEL_DIR/name).is_file() and (MODEL_DIR/name).stat().st_size == size
               for name, (_, size) in FILES.items())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_parakeet() -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("Instala huggingface_hub: pip install huggingface_hub") from exc
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (expected, size) in FILES.items():
        target = MODEL_DIR/name
        if target.is_file() and target.stat().st_size == size and sha256(target) == expected:
            print("[modelo] Ya verificado:",name,flush=True)
            continue
        print("[modelo] Descargando y verificando",name,"(",round(size/1e6),"MB )",flush=True)
        result = Path(hf_hub_download(repo_id=MODEL_REPO, filename=name,
                    revision=MODEL_REVISION, local_dir=str(MODEL_DIR)))
        actual = sha256(result)
        if result.stat().st_size != size or actual != expected:
            print(f"[modelo] Integridad no coincide para {name}: obtenido {actual}, esperado {expected}",flush=True)
            # Retry only the bad file; never re-download the 652 MB encoder.
            result.unlink(missing_ok=True)
            result = Path(hf_hub_download(
                repo_id=MODEL_REPO, filename=name, revision=MODEL_REVISION,
                local_dir=str(MODEL_DIR), force_download=True))
            actual = sha256(result)
            if result.stat().st_size != size or actual != expected:
                # Never install unverified model weights.
                result.unlink(missing_ok=True)
                raise RuntimeError(
                    f"SHA-256 incorrecto para {name}, incluso tras reintentar. "
                    f"Obtenido {actual}; esperado {expected}. "
                    "Se mantendra el motor Whisper. Comprueba conexion o antivirus."
                )
        print("[modelo] Correcto:",name,flush=True)
    print("[modelo] Parakeet instalado y verificado. Se ejecuta sin conexión.",flush=True)


class ParakeetRecognizer:
    name = "Parakeet v3 (sherpa-onnx)"
    def __init__(self):
        if not has_parakeet():
            raise RuntimeError(
                "Falta el modelo Parakeet. Ejecuta INSTALAR_MOTOR_COUCOU_HOVER.bat"
            )
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError(
                "Falta sherpa-onnx. Ejecuta INSTALAR_MOTOR_COUCOU_HOVER.bat"
            ) from exc
        self.rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(MODEL_DIR/"encoder.int8.onnx"),
            decoder=str(MODEL_DIR/"decoder.int8.onnx"),
            joiner=str(MODEL_DIR/"joiner.int8.onnx"),
            tokens=str(MODEL_DIR/"tokens.txt"),
            num_threads=min(4,os.cpu_count() or 2),
            provider="cpu", debug=False,
            decoding_method="greedy_search", model_type="nemo_transducer",
        )

    def transcribe(self, audio):
        stream = self.rec.create_stream()
        stream.accept_waveform(16000, audio)
        self.rec.decode_stream(stream)
        return (stream.result.text or "").strip()


class WhisperRecognizer:
    name = "Whisper Small (faster-whisper)"
    def __init__(self, model="small"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model, device="cpu", compute_type="int8")

    def transcribe(self, audio):
        # Coucou's wake-word examples motivate a contextual vocabulary for the
        # fallback. Temperature zero avoids some Whisper hallucinations.
        segments, _ = self.model.transcribe(
            audio, language="es", beam_size=5, temperature=0,
            condition_on_previous_text=False, vad_filter=False,
            initial_prompt=(
                "El usuario habla español con HOVER, su asistente de Windows. "
                "Oye Hover, abre el explorador de archivos. "
                "Oye Hover, cierra el explorador de archivos. "
                "Oye Hover, abre Paint. Abre Visual Studio Code. "
                "Abre el bloc de notas. Crea un Excel en Documentos. "
                "Cierra la ventana actual. Hover, bye bye. "
                "ChatGPT, Claude, Spotify, Google Drive, Gmail."
            ),
            no_speech_threshold=0.5,
            hallucination_silence_threshold=1.0,
        )
        chunks = []
        for segment in segments:
            if segment.no_speech_prob >= 0.7 or segment.avg_logprob < -1.3:
                continue
            chunks.append(segment.text.strip())
        return " ".join(chunks).strip()


def create_recognizer(engine="auto", whisper_model="small"):
    if engine == "parakeet" or (engine == "auto" and has_parakeet()):
        recognizer = ParakeetRecognizer()
    elif engine in ("whisper","auto"):
        recognizer = WhisperRecognizer(whisper_model)
    else:
        raise ValueError("Motor permitido: auto, parakeet, whisper")
    print("[motor]",recognizer.name,flush=True)
    return recognizer

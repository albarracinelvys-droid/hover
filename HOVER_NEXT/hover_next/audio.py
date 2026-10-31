"""Microphone capture and energy-based speech segmentation for HOVER.

This module never saves or uploads audio. Wake detection happens later.
"""
from __future__ import annotations

from collections import deque
from queue import Queue, Full, Empty
import time
import numpy as np


class SpeechSegmenter:
    """Consume 30 ms mono frames at 16 kHz; yield utterances after silence."""

    def __init__(self, threshold: float = 0.0008, sample_rate: int = 16000,
                 frame_ms: int = 30, start_ms: int = 120,
                 silence_ms: int = 750, max_seconds: float = 12.0):
        if not (0 < threshold < 1):
            raise ValueError("El umbral de voz debe ser mayor que 0 y menor que 1.")
        self.threshold = threshold
        self.frame_length = sample_rate * frame_ms // 1000
        self.start_frames = max(1, (start_ms + frame_ms - 1) // frame_ms)
        self.silence_frames = max(1, (silence_ms + frame_ms - 1) // frame_ms)
        self.max_frames = max(self.silence_frames + 1, int(max_seconds * 1000 / frame_ms))
        self.preroll = deque(maxlen=max(5, int(450 / frame_ms)))
        self.active = False
        self.frames = []
        self.onset = self.silent = self.voiced = 0
        self.last_rms = 0.0

    def process(self, frame: np.ndarray):
        mono = np.asarray(frame, dtype=np.float32).reshape(-1)
        if mono.size != self.frame_length:
            raise ValueError(f"Se esperaban {self.frame_length} muestras; llegaron {mono.size}.")
        rms = float(np.sqrt(np.mean(mono * mono)))
        self.last_rms = rms
        speech = rms >= self.threshold

        if not self.active:
            self.preroll.append(mono.copy())
            self.onset = self.onset + 1 if speech else 0
            if self.onset >= self.start_frames:
                self.active = True
                self.frames = list(self.preroll)
                self.voiced = self.onset
                self.silent = 0
                self.preroll.clear()
            return None

        self.frames.append(mono.copy())
        if speech:
            self.voiced += 1
            self.silent = 0
        else:
            self.silent += 1

        if self.silent >= self.silence_frames or len(self.frames) >= self.max_frames:
            result = np.concatenate(self.frames)
            enough_speech = self.voiced >= self.start_frames
            self.active = False
            self.frames = []
            self.onset = self.silent = self.voiced = 0
            self.preroll.clear()
            return result if enough_speech else None
        return None


def _resample(frame: np.ndarray, out_len: int) -> np.ndarray:
    """Linearly resample one 30 ms input block to 480 samples (16 kHz)."""
    mono = np.asarray(frame, dtype=np.float32).reshape(-1)
    if len(mono) == out_len:
        return mono.copy()
    indices = np.linspace(0, len(mono) - 1, out_len, dtype=np.float64)
    return np.interp(indices, np.arange(len(mono)), mono).astype(np.float32)


def microphone_events(device=None, threshold: float = 0.0008, diagnostic=False,
                      duration: float | None = None):
    """Yield ('segment', audio) or ('meter', rms). No audio is written to disk."""
    import sounddevice as sd

    info = sd.query_devices(device, kind="input")
    input_rate = int(round(info["default_samplerate"]))
    if input_rate <= 0:
        input_rate = 48000

    print(f"[mic] {info['name']} | dispositivo={device if device is not None else 'predeterminado'} "
          f"| {input_rate} Hz", flush=True)
    print(f"[mic] Umbral de voz {threshold:.5f}. Habla cerca del micrófono.", flush=True)

    frames = Queue(maxsize=180)
    frame_ms = 30
    input_samples = int(round(input_rate * frame_ms / 1000))
    output_samples = 16000 * frame_ms // 1000
    segmenter = SpeechSegmenter(threshold=threshold)
    warnings = 0

    def callback(indata, frame_count, time_info, status):
        nonlocal warnings
        if status:
            warnings += 1
        try:
            frames.put_nowait(indata[:, 0].copy())
        except Full:
            warnings += 1

    started = time.monotonic()
    next_meter = started + (0.5 if diagnostic else 2.0)

    with sd.InputStream(device=device, samplerate=input_rate, channels=1,
                        dtype="float32", blocksize=input_samples, callback=callback):
        while duration is None or time.monotonic() - started < duration:
            try:
                samples = frames.get(timeout=0.3)
            except Empty:
                if time.monotonic() >= next_meter:
                    print("[mic] Aún esperando paquetes de audio...", flush=True)
                    next_meter = time.monotonic() + 2.0
                continue

            resampled = _resample(samples, output_samples)
            utterance = segmenter.process(resampled)
            now = time.monotonic()

            if now >= next_meter:
                print(f"[mic] RMS={segmenter.last_rms:.5f} | umbral={threshold:.5f} | "
                      f"hablando={'si' if segmenter.active else 'no'} | avisos={warnings}",
                      flush=True)
                next_meter = now + (0.5 if diagnostic else 2.0)

            if utterance is not None and not diagnostic:
                print(f"[asr] Voz detectada: {len(utterance)/16000:.1f} s; transcribiendo...",
                      flush=True)
                yield ("segment", utterance)
                # Avoid executing very old audio stored while Whisper was processing.
                dropped = 0
                while dropped < 160:
                    try:
                        frames.get_nowait()
                    except Empty:
                        break
                    dropped += 1
                if dropped:
                    print(f"[mic] {dropped} bloques antiguos descartados tras la transcripción.",
                          flush=True)
            elif diagnostic:
                yield ("meter", segmenter.last_rms)

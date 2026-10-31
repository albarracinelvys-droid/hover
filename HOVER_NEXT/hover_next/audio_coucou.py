"""Coucou-inspired speech VAD for HOVER, independent of any ASR engine.

The VAD keeps a recent noise floor, buffers 360 ms of preroll, rejects
short clicks, and ends a phrase after 540 ms of silence. All audio is RAM-only.
Coucou's Windows project uses the same two-stage (VAD -> STT) approach.
"""
from __future__ import annotations

from collections import deque
import numpy as np

SAMPLE_RATE = 16000
FRAME = 480  # 30 ms


class AdaptiveVad:
    def __init__(self, minimum_rms: float = 0.0008,
                 hangover_frames: int = 18, max_frames: int = 380):
        if not 0 < minimum_rms < 0.2:
            raise ValueError("minimum_rms debe ser mayor a 0 y menor a 0.2")
        if not 10 <= hangover_frames <= 40:
            raise ValueError("hangover_frames debe estar entre 10 y 40.")
        self.minimum_rms = minimum_rms
        self.floor = 0.0001
        self.hangover_frames = hangover_frames
        self.max_frames = max_frames
        self.preroll = deque(maxlen=12)
        self.current = []
        self.active = False
        self.onset = 0
        self.silence = 0
        self.voice_frames = 0
        self.rms = 0.0
        self.threshold = minimum_rms

    def reset(self):
        self.preroll.clear()
        self.current = []
        self.active = False
        self.onset = 0
        self.silence = 0
        self.voice_frames = 0

    def feed(self, samples: np.ndarray) -> np.ndarray | None:
        frame = np.asarray(samples, dtype=np.float32).reshape(-1)
        if frame.size != FRAME:
            raise ValueError("Se esperaba un bloque de 480 muestras a 16 kHz.")
        frame = np.nan_to_num(frame, nan=0.0, posinf=0.0, neginf=0.0)
        self.rms = float(np.sqrt(np.mean(frame * frame)))
        self.threshold = max(self.minimum_rms, 3.0 * self.floor)
        speech = self.rms >= self.threshold
        if not self.active:
            if not speech:
                self.floor = min(0.025, 0.96 * self.floor + 0.04 * self.rms)
                self.onset = 0
            else:
                self.onset += 1
            self.preroll.append(frame.copy())
            # 150 ms of consistent sound is required; one loud click fails.
            if self.onset >= 5:
                self.active = True
                self.voice_frames = self.onset
                self.current = list(self.preroll)
                self.silence = 0
                self.preroll.clear()
            return None

        self.current.append(frame.copy())
        if speech:
            self.voice_frames += 1
            self.silence = 0
        else:
            self.silence += 1

        if self.silence >= self.hangover_frames or len(self.current) >= self.max_frames:
            total = len(self.current)
            enough = self.voice_frames >= 10 and total >= 16
            output = np.concatenate(self.current) if enough else None
            self.reset()
            return output
        return None


def resample_frame(samples: np.ndarray, size: int = FRAME) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if len(samples) == size:
        return samples.copy()
    if len(samples) < 2:
        return np.zeros(size, dtype=np.float32)
    coords = np.linspace(0, len(samples) - 1, size)
    return np.interp(coords, np.arange(len(samples)), samples).astype(np.float32)


def normalize_audio(samples: np.ndarray) -> np.ndarray:
    """Moderate automatic gain. Do not amplify total silence or clip input."""
    audio = np.nan_to_num(np.asarray(samples, dtype=np.float32), copy=True)
    if len(audio) == 0:
        return audio
    percentile = float(np.percentile(np.abs(audio), 95))
    if percentile < 0.00005:
        return audio
    gain = min(12.0, max(1.0, 0.13 / percentile))
    return np.clip(audio * gain, -0.95, 0.95)

"""Detect the explicit HOVER wake phrase in Whisper transcripts.

Punctuation is normalized for phrases such as "Oye, ¿jover?".
A wake word is not proof of speaker identity.
"""
from __future__ import annotations

import re
import unicodedata

_WAKE = re.compile(
    r"^(?:oye|oie|oi|hey|hola|huji|uji|huyi)\s+"
    r"(?:hover|jover|over|llover|hober|huver)\b"
)


def normalize_speech(text: str) -> str:
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(ch)
    )
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def extract_wake(text: str) -> str | None:
    """Return the spoken command after the wake phrase, or None if absent.

    An empty string means the wake phrase was recognized without a command.
    """
    normalized = normalize_speech(text)
    match = _WAKE.match(normalized)
    return normalized[match.end():].strip() if match else None

"""Voice-to-chat routing. A deliberately small, predictable Siri-like command set.

The instruction body keeps original punctuation and capitalization. Routing
metadata is never mixed into the user's message.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatRequest:
    provider: str
    project: str = ""
    prompt: str = ""


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def provider_name(text: str) -> str:
    t = _norm(text)
    if re.search(r"\b(?:chat\s*gpt|chatgpt|chat\s*gepete|chat\s*e\s*pepe|cati\s*petit)\b", t):
        return "chatgpt"
    if re.search(r"\b(?:claude|cloud|clau|clod)\b", t):
        return "claude"
    return ""


# Do not treat arbitrary questions containing "escribe" as browser operations.
_COMPOSE = re.compile(
    r"\b(?:escr[ií]bele|escr[ií]be(?:le)?|d[ií]le|env[ií]ale|"
    r"manda(?:le)?|preg[uú]ntale)"
    r"\s+(?:(?:lo|el)\s+siguiente|este\s+mensaje|este\s+prompt)\b"
    r"\s*[:;,\-]?\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_PROJECT = re.compile(
    r"\bproyecto\s+(?:(?:de|en)\s+)?"
    r"(?:(?:chat\s*gpt|chatgpt|chat\s*gepete)\s+)?"
    r"([a-zA-Z0-9][a-zA-Z0-9_-]{0,60})\b",
    re.IGNORECASE,
)
_NEW_CHAT_AFTER_MARKER = re.compile(
    r"^(?:en\s+)?(?:un\s+)?(?:nuevo\s+chat|nueva\s+conversaci[oó]n)"
    r"\s*[:;,.\-]?\s*",
    re.IGNORECASE,
)
_WAKE = re.compile(
    r"^\s*(?:(?:oye|hey|hola|huji|uji)\s*[,¿?¡! ]*)?"
    r"(?:hover|jover|over|llover|huver|hober|hoguer|joven)\b\s*[,¿?¡!. ]*",
    re.IGNORECASE,
)


def parse_chat_request(utterance: str) -> ChatRequest | None:
    text = _WAKE.sub("", utterance.strip(), count=1)
    provider = provider_name(text)
    if not provider:
        return None
    marker = _COMPOSE.search(text)
    if not marker:
        return None
    preamble = text[:marker.start()]
    # No user prompt without an explicit chat/open/send instruction.
    if not re.search(r"\b(?:abre|abrir|entra|accede|nuevo|nueva|chat|pesta[nñ]a|proyecto)\b", _norm(preamble)):
        return None
    project = ""
    project_match = _PROJECT.search(preamble)
    if project_match:
        project = _norm(project_match.group(1))
    prompt = marker.group(1).strip()
    prompt = _NEW_CHAT_AFTER_MARKER.sub("", prompt).strip()
    if not prompt or _norm(prompt) in ("en un nuevo chat", "un nuevo chat", "en una nueva conversacion"):
        prompt = ""
    return ChatRequest(provider=provider, project=project, prompt=prompt)

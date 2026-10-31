"""Siri-like ChatGPT/Claude speech commands without an LLM or shell access.

Examples:
  Oye Hover, abre ChatGPT y pregúntale cómo está.
  Oye Hover, abre chat, repete y preguntarle cómo está.
  Hover, abre ChatGPT en proyecto Zap y escribe lo siguiente: Hola.
  Hover, abre Claude y escríbele lo siguiente en un nuevo chat.
The body of a dictated message remains separate from its destination.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


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
    # Whisper is known to produce "chat, repete" for "ChatGPT".
    if re.search(
        r"\b(?:chatgpt|chat\s*[,.;]?\s*(?:gpt|gepete|repete)"
        r"|chat\s*e\s*pepe|cati\s*petit)\b", t
    ):
        return "chatgpt"
    if re.search(r"\b(?:claude|cloud|clau|clod|clout|clouding|cloude)\b", t):
        return "claude"
    return ""


_EXPLICIT_TEXT = re.compile(
    r"\b(?:escr[ií]bele|escr[ií]be(?:le)?|d[ií]le|env[ií]ale|"
    r"manda(?:le)?|preg[uú]ntale|preguntarle)"
    r"\s+(?:(?:lo|el)\s+siguiente|este\s+mensaje|este\s+prompt)\b"
    r"\s*[:;,\-]?\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_DIRECT_TEXT = re.compile(
    r"\b(?:preg[uú]ntale|preguntarle|preg[uú]ntale|d[ií]le|"
    r"escr[ií]bele|escr[ií]be(?:le)?|env[ií]ale|manda(?:le)?)"
    r"\s*(?:[:;,\-]\s*)?(.*)$",
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
    r"(?:hover|jover|over|llover|huver|hober|hoguer|joven)\b"
    r"\s*[,¿?¡!. ]*",
    re.IGNORECASE,
)


def _question(text: str) -> str:
    """Turn an explicit 'pregúntale cómo está' into a chat-facing question."""
    prompt = text.strip()
    if not prompt:
        return ""
    # The speaker is asking *ChatGPT*, not requesting a question about
    # ChatGPT in the third person.
    if _norm(prompt).strip(" .?!¿¡") in ("como esta", "como estas"):
        return "¿Cómo estás?"
    if re.match(
        r"^(?:qu[eé]|c[oó]mo|cu[aá]l|cu[aá]nt[oa]s?|"
        r"d[oó]nde|qui[eé]n|cu[aá]ndo|por qu[eé])\b", prompt, re.IGNORECASE
    ):
        question = prompt.rstrip("?. ")
        question = question[:1].upper() + question[1:]
        return ("¿" if not question.startswith("¿") else "") + question + "?"
    return prompt


def parse_chat_request(utterance: str) -> ChatRequest | None:
    text = _WAKE.sub("", utterance.strip(), count=1)
    provider = provider_name(text)
    if not provider:
        return None

    explicit = _EXPLICIT_TEXT.search(text)
    marker = explicit or _DIRECT_TEXT.search(text)
    if not marker:
        return None
    preamble = text[:marker.start()]
    # Merely discussing a provider is not a command to send it a message.
    # The provider must be named BEFORE the send/ask verb, and the request
    # must explicitly open/enter a new chat or a configured project.
    if not provider_name(preamble):
        return None
    if not re.search(
        r"\b(?:abre|abrir|entra|accede|nuevo|nueva|chat|pesta[nñ]a|proyecto)\b",
        _norm(preamble),
    ):
        return None

    project_match = _PROJECT.search(preamble)
    project = _norm(project_match.group(1)) if project_match else ""
    prompt = _NEW_CHAT_AFTER_MARKER.sub("", marker.group(1).strip()).strip()
    if _norm(prompt).strip(" .") in (
        "en un nuevo chat", "un nuevo chat", "en una nueva conversacion"
    ):
        prompt = ""
    # Commands with "escribe lo siguiente" keep user text exactly; direct
    # questions are punctuated as questions for a natural chat experience.
    if not explicit:
        prompt = _question(prompt)
    return ChatRequest(provider=provider, project=project, prompt=prompt)

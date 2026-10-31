"""Strict spoken-name parser for HOVER's short follow-up dialogues.

Accept only simple names and reject commands, prompt injection, paths and
filler. Safe for TXT, folder and GitHub private repository names.
"""
from __future__ import annotations

import re
import unicodedata


def _normal(text: str) -> str:
    value = "".join(
        c for c in unicodedata.normalize("NFKD",text.casefold())
        if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^a-z0-9._ -]", " ", value).split())


def spoken_name(text: str, kind: str = "txt") -> str:
    if kind not in ("txt","folder","excel","repo"):
        return ""
    value = _normal(text).strip(" .-")
    # The current voice dialogue has explicitly asked for the name.
    value = re.sub(
        r"^(?:oye\s+)?(?:hover\s+)?"
        r"(?:(?:el|mi)\s+)?"
        r"(?:(?:nombre\s+(?:es|de)\s+)|(?:se\s+llam(?:a|e)\s+)|"
        r"(?:que\s+se\s+llam(?:a|e)\s+)|(?:llamad[oa]\s+)|"
        r"(?:ll[aá]malo\s+)|(?:ponle\s+))?",
        "",value
    ).strip(" .-")
    if kind=="repo":
        value=re.sub(r"\s+(?:en|como|de forma)\s+privad[oa]$", "",value)
        value=re.sub(r"\s+privad[oa]$", "",value)
    # Never treat a second sentence or arbitrary assistant instruction
    # as a name. The user may instead repeat the full command.
    parts=value.split()
    if not 1<=len(parts)<=4 or len(value)>80:
        return ""
    forbidden={"abre","abrir","borra","elimina","compra","paga","ejecuta",
               "reproduce","reproducelo","spotify","google","cancelar",
               "cancela","para","enviar","repo","repositorio","txt",
               "archivo","carpeta","crea","crear","github","que"}
    if any(part in forbidden for part in parts):
        return ""
    if not all(re.fullmatch(r"[a-z0-9][a-z0-9._-]*",part) for part in parts):
        return ""
    value="-".join(parts) if kind=="repo" else " ".join(parts)
    value=value.strip(" .-")
    return value if len(value)>=2 else ""

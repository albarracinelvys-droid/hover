"""Deterministic commands: Windows programs, documents and Google Workspace.

The first word of a natural-language request is often 'abre', 'crea' or
'muestra'. Unlike an LLM, this module only emits allowlisted operations.
"""
from __future__ import annotations

import re
import unicodedata

from .intent import Intent


def clean(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def _contains(text: str, *phrases: str) -> bool:
    return any(re.search(r"\b" + re.escape(p) + r"\b", text) for p in phrases)


def parse_direct(text: str) -> Intent | None:
    t = clean(text)
    launch = _contains(t, "abre", "abrir", "muestra", "muestrame",
                       "inicia", "ejecuta", "crea", "crear", "nuevo", "nueva")
    if not launch:
        return None
    new = _contains(t, "crea", "crear", "nuevo", "nueva")

    # Office: 'Word' means the desktop application, not Google Docs.
    if _contains(t, "word", "microsoft word"):
        return Intent("office_new", args={"kind": "word"})
    if _contains(t, "excel", "microsoft excel"):
        return Intent("office_new", args={"kind": "excel"})
    if _contains(t, "powerpoint", "power point", "microsoft powerpoint"):
        return Intent("office_new", args={"kind": "powerpoint"})

    if _contains(t, "calculadora", "calculator", "calc"):
        return Intent("windows_app", args={"app": "calculator"})
    if _contains(t, "bloc de notas", "notepad"):
        return Intent("windows_app", args={"app": "notepad"})
    if _contains(t, "paint"):
        return Intent("windows_app", args={"app": "paint"})
    if _contains(t, "explorador de archivos", "explorador de windows"):
        return Intent("windows_app", args={"app": "explorer"})

    google = {
        "google_drive": ("google drive", "mi drive", "abre drive", "drive de google"),
        "google_docs": ("google docs", "docs de google", "documentos de google",
                        "documento de google"),
        "google_sheets": ("google sheets", "sheets", "hoja de calculo",
                          "hojas de calculo", "hoja de google"),
        "google_slides": ("google slides", "presentaciones de google",
                          "presentacion de google"),
        "google_calendar": ("google calendar", "calendario de google", "google calendario",
                            "mi calendario"),
        "google_gmail": ("gmail", "correo de google", "mi correo", "correo electronico"),
        "google_maps": ("google maps", "mapas de google", "google mapas"),
        "google_meet": ("google meet", "meet de google"),
        "google_keep": ("google keep", "notas de google"),
        "google_youtube": ("youtube", "you tube"),
        "google_photos": ("google fotos", "google photos", "fotos de google"),
        "google_translate": ("traductor de google", "google translate"),
    }
    for service, aliases in google.items():
        if _contains(t, *aliases):
            if new and service in ("google_docs", "google_sheets", "google_slides"):
                service += "_new"
            return Intent("google_app", args={"service": service})

    # Only open selected or named documents. Never launch .exe/.lnk/.ps1.
    m = re.search(r"\b(?:abre|abrir|muestra|muestrame)\s+"
                  r"(?:(?:el|este|ese|un|mi)\s+)?(?:documento|archivo)\b"
                  r"\s*(.*)$", t)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"^(?:que se llama|llamado|llamada|de nombre)\s+", "", name)
        if name in ("", "este", "ese", "seleccionado", "actual", "que tengo seleccionado"):
            name = ""
        return Intent("open_document", args={"name": name})

    return None

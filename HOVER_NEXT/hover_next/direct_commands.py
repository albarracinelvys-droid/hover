"""Small, allowlisted Windows and Google command router.

HOVER understands words without using generated shell commands. Intent
resolution is deterministic and tested with actual Whisper transcriptions.
"""
from __future__ import annotations
import re
import unicodedata

from .intent import Intent


def clean(text: str) -> str:
    value = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def has(text: str, *phrases: str) -> bool:
    return any(re.search(r"\b" + re.escape(x) + r"\b", text) is not None
               for x in phrases)


MEDIA = (
    (r"^(?:pausa|pausar|deten|reanuda|continua|sigue|reproduce)\s+"
     r"(?:la\s+)?(?:musica|cancion|reproduccion)$", "play_pause"),
    (r"^(?:siguiente|pasa|salta)(?:\s+(?:la|a la))?\s+"
     r"(?:cancion|pista|musica)$", "next"),
    (r"^(?:anterior|vuelve)(?:\s+(?:la|a la))?\s+(?:cancion|pista)$"
     r"|^(?:cancion|pista)\s+anterior$", "previous"),
    (r"^(?:sube|aumenta)(?:\s+el)?\s+volumen$", "volume_up"),
    (r"^(?:baja|reduce)(?:\s+el)?\s+volumen$", "volume_down"),
    (r"^(?:silencia|silenciar|mute|quita el sonido|activa el silencio)$",
     "volume_mute"),
)

WEB_SHORTCUTS = {
    "github": ("github", "git hub"),
    "whatsapp": ("whatsapp", "whatsapp web", "wasap"),
    "outlook": ("outlook", "correo outlook"),
    "onedrive": ("onedrive", "one drive"),
    "discord": ("discord",),
    "linkedin": ("linkedin", "linked in"),
    "notion": ("notion",),
    "canva": ("canva",),
    "vercel": ("vercel",),
    "gemini": ("gemini",),
    "perplexity": ("perplexity",),
    "stackoverflow": ("stackoverflow", "stack overflow"),
}

GOOGLE_ALIASES = {
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
    "google_translate": ("traductor de google", "google translate", "traductor"),
}


def parse_direct(text: str) -> Intent | None:
    t = clean(text)

    # Do not close an arbitrary window; the executor verifies a Google tab.
    if re.fullmatch(r"(?:cierra|cerrar)\s+(?:(?:la|el)\s+)?"
                    r"(?:(?:pestana|ventana)\s+de\s+)?google", t):
        return Intent("close_google_tab")

    for regex, key in MEDIA:
        if re.fullmatch(regex, t):
            return Intent("media_key", args={"key": key})

    launching = has(t, "abre", "abrir", "muestra", "muestrame", "inicia",
                    "ejecuta", "crea", "crear", "nuevo", "nueva",
                    "redacta", "redactar", "entra", "visita")
    if not launching:
        return None
    new = has(t, "crea", "crear", "nuevo", "nueva")

    # Office means the locally installed Microsoft application.
    for office in ("word", "excel", "powerpoint"):
        if has(t, office):
            return Intent("office_new", args={"kind": office})
    if has(t, "power point"):
        return Intent("office_new", args={"kind": "powerpoint"})

    if re.fullmatch(r"(?:abre|abrir|muestra)\s+(?:(?:una|otra)\s+)?"
                    r"(?:(?:nueva|nuevo)\s+pestana\s+de\s+)?google", t):
        return Intent("google_app", args={"service": "google_home"})

    apps = {
        "calculator": ("calculadora", "calculator", "calc"),
        "notepad": ("bloc de notas", "notepad"),
        "paint": ("paint",),
        "explorer": ("explorador de archivos", "explorador de windows"),
        "task_manager": ("administrador de tareas", "task manager"),
        "terminal": ("terminal", "simbolo del sistema", "cmd"),
        "settings": ("configuracion de windows", "configuracion del sistema",
                     "ajustes de windows"),
        "downloads": ("descargas", "carpeta descargas", "mis descargas"),
    }
    for app, aliases in apps.items():
        if has(t, *aliases):
            return Intent("windows_app", args={"app": app})
    if has(t, "documentos", "mis documentos") and not has(t, "google", "word"):
        return Intent("windows_app", args={"app": "documents"})

    for site, aliases in WEB_SHORTCUTS.items():
        if has(t, *aliases):
            return Intent("open_link", args={"site": site})

    for service, aliases in GOOGLE_ALIASES.items():
        if not has(t, *aliases):
            continue
        if service == "google_calendar" and new and has(t, "evento", "cita"):
            return Intent("google_app", args={"service": "google_calendar_new"})
        if service == "google_gmail" and has(
                t, "redacta", "redactar", "nuevo correo",
                "nuevo mensaje", "escribir correo"):
            return Intent("google_app", args={"service": "google_gmail_compose"})
        if new and service in ("google_docs", "google_sheets", "google_slides"):
            service += "_new"
        return Intent("google_app", args={"service": service})

    # Only allow documents, not executable files.
    match = re.search(r"\b(?:abre|abrir|muestra|muestrame)\s+"
                      r"(?:(?:el|este|ese|un|mi)\s+)?(?:documento|archivo)\b"
                      r"\s*(.*)$", t)
    if match:
        name = match.group(1).strip()
        name = re.sub(r"^(?:que se llama|llamado|llamada|de nombre)\s+", "", name)
        if name in ("", "este", "ese", "seleccionado", "actual",
                    "que tengo seleccionado"):
            name = ""
        return Intent("open_document", args={"name": name})

    return None

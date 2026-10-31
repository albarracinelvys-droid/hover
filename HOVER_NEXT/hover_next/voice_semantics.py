"""Small semantic layer for Spanish voice control.

This is an intent resolver, not a command generator. It accepts natural verbs
and known application aliases but NEVER executes arbitrary shell strings.
Potentially destructive system actions are NOT inferred fuzzily.
"""
from __future__ import annotations

import re

# The main parser already removes diacritics and wake words.
VERB_OPEN = r"(?:abre|abrir|abreme|inicia|iniciar|ejecuta|ejecutar|lanza|muestra|muestrame|pon|quiero\s+abrir)"
VERB_CLOSE = r"(?:cierra|cerrar|cierrame|cerrame|termina|sierra)"
LEAD = r"(?:(?:por\s+favor|oye|hey)\s+)?(?:(?:me\s+puedes|puedes|podrias|necesito\s+que|quiero\s+que|hazme\s+el\s+favor\s+de)\s+)?"
ART = r"(?:(?:el|la|los|las|mi|un|una)\s+)?"

_APPS = {
    "paint":("paint","pint"),
    "calculator":("calculadora","calc","calculator"),
    "explorer":("explorador","explorador de archivos","explorador de windows","explorer","explorer de archivos"),
    "notepad":("bloc de notas","notepad"),
    "vscode":("visual studio code","vs code","visual code","visual","codigo visual"),
    "terminal":("terminal","cmd","simbolo del sistema"),
    "task_manager":("administrador de tareas","task manager"),
    "excel":("excel","microsoft excel"),
    "word":("word","microsoft word"),
    "powerpoint":("power point","powerpoint"),
}


def _app(text: str) -> str | None:
    cleaned=re.sub(r"\s+"," ",text).strip(" .,")
    for app,aliases in _APPS.items():
        if cleaned in aliases:
            return app
    return None


def parse_flexible(text: str):
    """Return (action,args) only for wholly understood Windows intents."""
    t=re.sub(r"\s+"," ",text).strip(" .,!?¿¡")
    # Questions such as "cómo cerrar Word" are NEVER operations.
    if re.match(r"^(?:como|que|por que|puedo|podrias\s+explicarme|explica)\b",t):
        return None

    pattern=LEAD+VERB_CLOSE+r"\s+"+ART+r"(.+)"
    m=re.fullmatch(pattern,t)
    if m:
        subject=m.group(1).strip()
        # Never interpret arbitrary process names as kill commands.
        if subject in ("ventana","ventana actual","ventana activa","esta ventana",
                       "programa actual","programa activo","aplicacion actual",
                       "aplicacion activa","esto"):
            return "pc_close_window",{"app":"foreground"}
        app=_app(subject)
        if app in ("vscode","explorer","paint","notepad","calculator","excel",
                   "word","powerpoint","terminal","task_manager"):
            return "pc_close_window",{"app":app}
        return None

    m=re.fullmatch(LEAD+VERB_OPEN+r"\s+"+ART+r"(.+)",t)
    if m:
        subject=m.group(1).strip()
        app=_app(subject)
        if app in ("paint","calculator","explorer","notepad","vscode","terminal",
                   "task_manager"):
            return "windows_app",{"app":app}
        if app in ("excel","word","powerpoint"):
            return "office_new",{"kind":app}
        return None
    return None

"""Explicit voice controls for the user's connected Google account.

Ordinary public questions remain Google web searches; private account data
is never forwarded to ChatGPT or Claude without a named destination and a
separate confirmation. No inferred provider credential sharing.
"""
from __future__ import annotations

import re
import unicodedata


def norm(text):
    txt="".join(x for x in unicodedata.normalize("NFKD",text.casefold())
                if not unicodedata.combining(x))
    return " ".join(txt.strip(" ,.;:?!¿¡").split())


def parse_google_command(spoken):
    t=norm(spoken)
    m=re.fullmatch(
        r"(?:conecta|conectar|vincula|autoriza|desconecta|desconectar)"
        r"\s+(?:(?:mi|la)\s+)?(?:(?:cuenta|servicio)\s+(?:de\s+)?)?"
        r"(google|gmail|drive|google drive|calendar|calendario|"
        r"google calendar|docs|google docs)",t)
    if m:
        key=m.group(1)
        service=("gmail" if "gmail" in key else "drive" if "drive" in key else
                 "calendar" if "calendar" in key or "calendario" in key else
                 "docs" if "docs" in key else "all")
        action="google_disconnect" if t.startswith("desconecta") else "google_connect"
        return action,{"service":service},False

    if re.fullmatch(
        r"(?:estado|cuenta|conexion|conexiones)\s+(?:de\s+)?google"
        r"|(?:que|cuales)\s+(?:cuentas|servicios)\s+google"
        r"\s+(?:tengo\s+)?conectad[oa]s?",t):
        return "google_status",{},False

    # Explicit event phrases work without the optional Ollama server.
    # Example: "crea un evento para mañana que diga materia nula todo el día".
    m=re.fullmatch(
        r"(?:crea|crear|creame|agenda|agendar|programa|programar)\\s+"
        r"(?:(?:un|un nuevo)\\s+)?(?:evento|recordatorio|cita)\\s+"
        r"(?:para|el)\\s+(.+?)\\s+"
        r"(?:que\\s+(?:diga|se\\s+llame)|llamad[oa]|titulado)\\s+"
        r"(.+?)"
        r"(?:\\s+(todo\\s+el\\s+dia|durante\\s+todo\\s+el\\s+dia|"
        r"sin\\s+hora|a\\s+las\\s+.+))?$",t)
    if m:
        date_phrase=m.group(1).strip()
        title=m.group(2).strip()
        schedule=(m.group(3) or "").strip()
        if schedule in ("todo el dia","durante todo el dia","sin hora"):
            schedule=""
        if 2<=len(date_phrase)<=100 and 2<=len(title)<=120:
            return "google_create_event",{
                "title":title,"date_phrase":date_phrase,
                "time_phrase":schedule},False

    # "crea un documento de Google llamado Informe semanal"
    m=re.fullmatch(
        r"(?:crea|crear|creame)\s+(?:(?:un|nuevo)\s+)?"
        r"(?:documento\s+(?:en|de)\s+google|google\s+docs|doc)"
        r"\s+(?:llamad[oa]|que\s+se\s+llame|con\s+nombre)\s+(.+)",t)
    if m:
        return "google_create_doc",{"title":m.group(1)},False

    # Sharing private Google search metadata requires explicit destination
    # and separate consent before sending anything to another company.
    m=re.fullmatch(
        r"(?:busca|buscar|encuentra)\s+(.+?)"
        r"\s+(?:en|dentro\s+de)\s+(?:mi\s+)?"
        r"(?:cuenta\s+de\s+google|google\s+drive|drive|gmail|"
        r"calendario|calendar|google\s+docs|docs)"
        r"\s+y\s+(?:envia(?:lo|s)?|mandalo|compartelo|preguntale)"
        r"\s+(?:a|con)\s+(chatgpt|chat\s*gpt|claude|cloud)",t)
    if m:
        source=_source_from_phrase(t)
        provider="claude" if m.group(2) in ("claude","cloud") else "chatgpt"
        return "google_share_ai",{"query":m.group(1),
                                  "source":source,"provider":provider},True

    # Explicit private searches, including "mis correos", "mis archivos".
    m=re.fullmatch(
        r"(?:busca|buscar|encuentra|revisa|consulta|muestra)"
        r"\s+(.+?)\s+(?:en|dentro\s+de)\s+"
        r"(?:mi\s+)?(?:cuenta\s+(?:de\s+)?google|drive|google\s+drive|"
        r"gmail|correo|calendario|calendar|google\s+docs|docs)",t)
    if m:
        return "google_personal_search",{
            "query":m.group(1),"source":_source_from_phrase(t)},False

    m=re.fullmatch(
        r"(?:busca|buscar|revisa|consulta|muestra)\s+(?:en\s+)?"
        r"(?:mi\s+)?(drive|gmail|correo|calendario|calendar|"
        r"google\s+docs|docs|cuenta\s+de\s+google)"
        r"\s+(?:sobre|de|con|que\s+conteng(?:a|an))\s+(.+)",t)
    if m:
        return "google_personal_search",{
            "query":m.group(2),"source":_source_from_phrase(t)},False

    m=re.fullmatch(
        r"(?:revisa|muestra|busca|consulta)\s+"
        r"(?:mis\s+)?(?:correos|emails|mensajes|archivos|documentos)"
        r"\s+(?:sobre|de|que\s+conteng(?:a|an))\s+(.+)",t)
    if m:
        source="gmail" if any(x in t for x in ("correos","emails","mensajes")) else "drive"
        return "google_personal_search",{"query":m.group(1),"source":source},False

    return None


def _source_from_phrase(value):
    if any(q in value for q in ("gmail","correo")): return "gmail"
    if any(q in value for q in ("calendar","calendario")):return "calendar"
    if any(q in value for q in ("docs","documento de google")):return "docs"
    if "drive" in value:return "drive"
    return "all"

#!/usr/bin/env python3
"""HOVER voz v4.1: reconocimiento offline Vosk y acciones locales limitadas.

Activación: «Oye Hover» / «Oye Jover». Sin API externa ni captura permanente
almacenada: los fragmentos del micrófono se procesan en memoria.

No ejecuta órdenes arbitrarias del sistema. Los eventos .ics requieren confirmar
la importación en la aplicación de calendario; no se añaden silenciosamente.

Prueba sin micrófono/modelo: python Asistente_Voz_HOVER_v4.py --texto
"""
from __future__ import annotations

import argparse
import json
import difflib
import threading
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

BASE = Path(tempfile.gettempdir()) / "WindhawkIslandPremium"
HOME = Path(os.environ.get("APPDATA", str(Path.home()))) / "HOVER"
BASE.mkdir(parents=True, exist_ok=True)
HOME.mkdir(parents=True, exist_ok=True)
UI_FILE = BASE / "voice_ui.txt"
TABS_FILE = BASE / "voice_tabs.txt"
DATA_FILE = HOME / "pestanas_voz.json"
MAX_TABS = 5
PAGE_NAMES = ["musica", "copias", "calendario", "atajos", "equipo"]

SITES = {
    "chatgpt": "https://chatgpt.com/",
    "chat gpt": "https://chatgpt.com/",
    "claude": "https://claude.ai/new",
    "github": "https://github.com/",
    "git hub": "https://github.com/",
    "youtube": "https://www.youtube.com/",
    "you tube": "https://www.youtube.com/",
    "gmail": "https://mail.google.com/",
    "correo": "https://mail.google.com/",
    "google": "https://www.google.com/",
    "spotify": "https://open.spotify.com/",
    "outlook": "https://outlook.live.com/calendar/",
}

# Sonidos habituales de «Hover» en el modelo espanol de Vosk.
WAKE = re.compile(
    r"\b(?:(?:oye|hey|ei|ok|hola)\s+(?:hover|jover|over|hober|hoover|ober|joe|jobe|yover)|dejo el)\b",
    re.I,
)
TRAILING_WAKE = re.compile(r"\s+(?:hover|jover|over|hober|hoover)\s*$",re.I)
_TTS_BUSY = threading.Event()

# El modelo pequeno suele transcribir los nombres ingleses de manera fonetica.
# Son ALIAS de comandos conocidos: no permite ejecutar ordenes arbitrarias.
SITE_PHONETICS = {
    "chatgpt": [
        "chat gpt", "chat ge pe te", "chat ge pete", "chat gepete",
        "chat e pepe", "chat e pete", "chat pete", "chat jep", "chat jepe",
        "chat e pretende", "chat e pretendi", "chat e pretendo", "chat gp",
        "chat gep", "chat ye pe te", "cati piti", "cati peti", "chat yipiti",
        "chati piti", "chat gepiti", "chat yi pi ti", "chat piti", "chat g p t",
        "chat e p t", "chat chipe te", "chat e pepe te", "calle petty", "calle peti", "calle petti", "calle piti",
    ],
    "spotify": ["espotifai", "espotify", "spotifai", "espotifay", "spotifay"],
    "claude": ["clau", "claud", "claudio"],
}


def canonical_command(value: str) -> str:
    t = norm(value).strip(" .,!?¿¡")
    # Proteger las partes informativas de eventos y nombres de pestana:
    # solo se corrigen los nombres de sitios/comandos conocidos.
    for name, alternatives in SITE_PHONETICS.items():
        for alias in sorted(alternatives, key=len, reverse=True):
            t = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", name, t)
    t = re.sub(r"^(?:accede|acceda|accede|acces|aces|acede|acedea|acceso|entra|ingresa|visita)\s+(?:a\s+|al\s+)?", "abre ", t)
    t = re.sub(r"^(?:alli se ha|alise a|alise ha|dale a)\s+(chatgpt|spotify|claude)\b", r"abre \1",t)
    t = re.sub(r"^(?:abrir|habre|abra)\s+", "abre ", t)
    t = re.sub(r"^(?:muestreme|muestrame)\s+", "muestra ", t)
    return t


def transcript_score(raw: str) -> float:
    """Prioriza alternativas con wake word y una accion conocida; no fabrica acciones."""
    spoken=norm(raw)
    canon=canonical_command(spoken)
    score = 0.0
    if WAKE.search(spoken): score+=5.0
    if re.search(r"\b(?:abre|reproduce|muestra|crea|configura|agrega|siguiente|ayuda)\b",canon):score+=2.0
    if any(site in canon for site in ("chatgpt", "spotify", "claude")):score+=2.0
    if canon != spoken:score+=0.5
    return score


def best_vosk_result(result: dict) -> str:
    """Compatibilidad con Result normal y SetMaxAlternatives."""
    alternatives=result.get("alternatives")
    if not isinstance(alternatives,list) or not alternatives:
        return str(result.get("text", ""))
    scored=[]
    for a in alternatives:
        if isinstance(a,dict):
            transcript=str(a.get("text", ""))
            # Confianza ASR pesa mas que una variante arbitraria, pero menos que wake+intencion.
            scored.append((transcript_score(transcript)+float(a.get("confidence",0.0))*1.3,transcript))
    return max(scored,default=(0.0,""))[1]

STATE_SERIAL = 0
SPEAK_ENABLED = False


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip()


def clean_line(text: str, max_length: int = 100) -> str:
    return re.sub(r"[\t\r\n]+", " ", text).strip()[:max_length]


def write_atomic(path: Path, text: str) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def speak(message: str) -> None:
    """SAPI local, en un hilo; no interrumpe la lectura del microfono.

    Pausa el procesamiento de audio mientras suena la voz sintetica para
    impedir que HOVER se escuche y se active a si mismo.
    """
    if not SPEAK_ENABLED or sys.platform != "win32" or _TTS_BUSY.is_set():
        return
    import base64
    safe=clean_line(message,120).replace("'","''")
    script=("$ErrorActionPreference='Stop'; "
            "$voice=New-Object -ComObject SAPI.SpVoice; "
            "$voice.Speak('"+safe+"') | Out-Null")
    encoded=base64.b64encode(script.encode("utf-16le")).decode("ascii")
    _TTS_BUSY.set()
    def worker():
        try:
            subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                            "-EncodedCommand",encoded],timeout=15,
                           check=False,capture_output=True)
        except (OSError,subprocess.TimeoutExpired):
            pass
        finally:
            time.sleep(0.35)
            _TTS_BUSY.clear()
    threading.Thread(target=worker,daemon=True,name="HOVER-SAPI").start()


def notify(mode: str, message: str, page: int = -1) -> None:
    global STATE_SERIAL
    STATE_SERIAL += 1
    serial = f"{os.getpid()}-{STATE_SERIAL}-{time.monotonic_ns()}"
    write_atomic(UI_FILE, "\t".join([serial, mode, str(page), clean_line(message, 115)]))
    print(f"[{mode}] {message}" + (f" (modulo {page})" if page != -1 else ""), flush=True)


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http") and bool(parsed.hostname) and not parsed.username


def resolve_site(text: str) -> str | None:
    key = canonical_command(text)
    # Only allow a known site or an explicitly spoken domain without whitespace.
    if key in SITES:
        return SITES[key]
    key = re.sub(r"^(?:la pagina de|el sitio|la web de|web de)\s+", "", key)
    if key in SITES:
        return SITES[key]
    domain = key.replace(" punto ", ".")
    if re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,10}", domain):
        return "https://" + domain
    if re.fullmatch(r"https?://[a-z0-9.-]+(?:/[a-z0-9/_-]*)?", domain):
        return domain if valid_url(domain) else None
    return None


def load_tabs() -> list[dict[str, str]]:
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        valid: list[dict[str, str]] = []
        for entry in data[:MAX_TABS]:
            if not isinstance(entry, dict):
                continue
            name = clean_line(str(entry.get("name", "")), 38)
            url = str(entry.get("url", ""))
            if name and (not url or valid_url(url)):
                valid.append({"name": name, "url": url})
        return valid
    except (OSError, ValueError, TypeError):
        return []


def save_tabs(tabs: list[dict[str, str]]) -> None:
    write_atomic(DATA_FILE, json.dumps(tabs[:MAX_TABS], ensure_ascii=False, indent=2))
    publish_tabs(tabs)


def publish_tabs(tabs: list[dict[str, str]] | None = None) -> None:
    tabs = load_tabs() if tabs is None else tabs
    # Unlike JSON, this format remains trivial to parse in native Win32.
    lines = [clean_line(t["name"], 38) + "\t" + t["url"] for t in tabs[:MAX_TABS]]
    write_atomic(TABS_FILE, "\n".join(lines) + ("\n" if lines else ""))


def current_page_for(name: str) -> int | None:
    key = norm(name)
    aliases = {"pc": "equipo", "mi pc": "equipo", "hardware": "equipo",
               "sistema": "equipo", "musica": "musica", "spotify": "musica",
               "copiar": "copias", "accesos": "atajos", "acceso": "atajos",
               "agenda": "calendario", "calendario": "calendario"}
    key = aliases.get(key, key)
    if key in PAGE_NAMES:
        return PAGE_NAMES.index(key)
    for i, tab in enumerate(load_tabs()):
        if norm(tab["name"]) == key:
            return len(PAGE_NAMES) + i
    return None


def open_spotify() -> bool:
    if sys.platform == "win32":
        try:
            os.startfile("spotify:")
            return True
        except OSError:
            pass
    return webbrowser.open(SITES["spotify"])


def status_spotify() -> tuple[bool, bool]:
    try:
        state = (BASE / "status.txt").read_text(encoding="utf-8")
        fields = dict(line.split("=", 1) for line in state.splitlines() if "=" in line)
        recent = time.time() - (BASE / "status.txt").stat().st_mtime < 4
        return (recent and "spotify" in fields.get("source", "").casefold(),
                fields.get("playing") == "1")
    except (OSError, ValueError):
        return False, False


def media_play() -> str:
    # Global Play key only when Spotify session becomes active; avoids pausing
    # some unrelated media session when just opening Spotify.
    if sys.platform != "win32":
        return "Spotify abierto en el navegador; pulsa Reproducir."
    try:
        import ctypes
        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xB3, 0, 0x0002, 0)
        return "Reproducción solicitada a Spotify."
    except (AttributeError, OSError):
        return "Spotify abierto; inicia la canción en el reproductor."


def show_my_pc() -> None:
    if sys.platform != "win32":
        raise OSError("Esta acción requiere Windows")
    subprocess.Popen(["explorer.exe", "shell:MyComputerFolder"])


def open_settings() -> None:
    if sys.platform != "win32":
        raise OSError("Esta acción requiere Windows")
    os.startfile("ms-settings:")


def ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
          "octubre": 10, "noviembre": 11, "diciembre": 12}
WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
            "sabado": 5, "domingo": 6}


def parse_event(text: str, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Parse 'reunion mañana a las 3 de la tarde' etc., local timezone.

    When ambiguous or missing a date/hour, return None and request clarification.
    """
    now = now or datetime.now().astimezone()
    base = norm(text)
    t = base
    day = None
    match = re.search(r"\b(hoy|manana|pasado manana|proximo (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo))\b", t)
    span = None
    if match:
        word = match.group(1)
        span = match.span()
        if word == "hoy": day = now.date()
        elif word == "manana": day = (now + timedelta(days=1)).date()
        elif word == "pasado manana": day = (now + timedelta(days=2)).date()
        else:
            target = WEEKDAYS[word.split()[-1]]
            diff = (target - now.weekday()) % 7
            day = (now + timedelta(days=diff if diff else 7)).date()
    if day is None:
        date_match = re.search(r"\b(?:el\s+)?(\d{1,2})\s+de\s+("+"|".join(MONTHS)+r")(?:\s+de\s+(\d{4}))?",t)
        if date_match:
            span = date_match.span()
            year = int(date_match.group(3)) if date_match.group(3) else now.year
            try:
                day = datetime(year, MONTHS[date_match.group(2)], int(date_match.group(1))).date()
                if not date_match.group(3) and day < now.date():
                    day = day.replace(year=year+1)
            except ValueError:
                return None
    if day is None:
        return None
    time_match = re.search(r"\b(?:a\s+las?|a\s+la)\s+(\d{1,2})(?::(\d{2}))?\s*(?:de\s+la\s+)?(manana|tarde|noche|am|pm)?",t)
    if not time_match:
        return None
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    part = time_match.group(3)
    if hour > 23 or minute > 59:
        return None
    if part in ("tarde", "noche", "pm") and hour < 12: hour += 12
    if part in ("manana", "am") and hour == 12: hour = 0
    if part is None and hour <= 12:
        # Avoid ambiguous 'a las 3' unless 24h format or time of day explicit.
        return None
    if span is None:
        return None
    # Remove date and time spans, then filler. Leave descriptive title.
    remove = [span, time_match.span()]
    title_chars = list(t)
    for a,b in remove:
        for i in range(a,b): title_chars[i] = " "
    title = " ".join("".join(title_chars).split())
    title = re.sub(r"^(?:evento|cita|recordatorio|reunion|para)\s+", "", title).strip()
    if not title: title="Nuevo evento"
    # Prevent dates with an explicit past year.
    when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
    if when < now - timedelta(minutes=5):
        return None
    return title[:90], when


def make_calendar_draft(details: str) -> tuple[str, Path] | None:
    parsed = parse_event(details)
    if not parsed:
        return None
    title, when = parsed
    root = HOME / "Eventos"
    root.mkdir(parents=True, exist_ok=True)
    start = when.astimezone(timezone.utc)
    end = (when + timedelta(hours=1)).astimezone(timezone.utc)
    stamped = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = root / (when.strftime("%Y%m%d_%H%M_") + uuid.uuid4().hex[:8] + ".ics")
    data = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HOVER//VOICE V4//ES",
        "BEGIN:VEVENT", "UID:" + uuid.uuid4().hex + "@hover.local",
        "DTSTAMP:" + stamped,
        "DTSTART:" + start.strftime("%Y%m%dT%H%M%SZ"),
        "DTEND:" + end.strftime("%Y%m%dT%H%M%SZ"),
        "SUMMARY:" + ics_escape(title),
        "END:VEVENT", "END:VCALENDAR", ""
    ])
    filename.write_bytes(data.encode("utf-8"))
    if sys.platform == "win32":
        try:
            os.startfile(str(filename))
        except OSError:
            # Keep the .ics and make it easy to find.
            subprocess.Popen(["explorer.exe", "/select,", str(filename)])
    return f"Evento preparado: {title}. Confirma Guardar en tu calendario.", filename


def process_command(command: str) -> tuple[str, int]:
    """Returns (feedback, optional HOVER page). No shell execution from speech."""
    t = canonical_command(command)
    if not t:
        return "Te escucho. Dime qué necesitas.", -1

    # Controlled custom tabs; never use shell or arbitrary file paths.
    create = re.fullmatch(r"(?:crea|crear|agrega|anade)\s+(?:una?\s+)?pestana(?:\s+llamada)?\s+(.+?)(?:\s+para\s+(?:abrir\s+)?(.+))?", t)
    if create:
        name = clean_line(create.group(1),38).title()
        dest = create.group(2)
        url = resolve_site(dest) if dest else ""
        if dest and not url:
            return "No reconozco ese sitio. Di por ejemplo GitHub o YouTube.", -1
        tabs = load_tabs()
        existing = next((i for i, tab in enumerate(tabs) if norm(tab["name"])==norm(name)),None)
        if existing is not None:
            return f"Ya existe la pestaña {name}. Puedes configurarla por voz.", len(PAGE_NAMES)+existing
        if len(tabs)>=MAX_TABS:
            return "Ya tienes cinco pestañas personalizadas, el máximo de esta versión.", -1
        tabs.append({"name":name,"url":url or ""})
        save_tabs(tabs)
        return f"Pestaña {name} creada"+(f" para {dest}." if dest else "."), len(PAGE_NAMES)+len(tabs)-1

    configure = re.fullmatch(r"(?:configura|cambia|modifica)\s+(?:la\s+)?pestana\s+(.+?)\s+para\s+(?:abrir\s+)?(.+)",t)
    if configure:
        name, dest = configure.groups()
        tabs = load_tabs()
        i = next((i for i, tab in enumerate(tabs) if norm(tab["name"])==norm(name)),None)
        if i is None:
            return f"No existe la pestaña {name}. Di: crea pestaña {name}.", -1
        url=resolve_site(dest)
        if not url:
            return "Necesito un sitio conocido, como GitHub, YouTube o ChatGPT.", -1
        tabs[i]["url"] = url
        save_tabs(tabs)
        return f"Pestaña {name} configurada para {dest}.",len(PAGE_NAMES)+i

    if t in ("crea pestana", "crear nueva pestana", "configura nueva pestana", "nueva pestana"):
        return "Di: crea pestaña Trabajo para GitHub, por ejemplo.", -1

    shortcut = re.fullmatch(r"(?:abre|ejecuta|accede a|inicia)\s+(?:el\s+)?atajo\s+(.+)",t)
    if shortcut:
        name=shortcut.group(1)
        if name in ("carpeta", "mi carpeta"):
            favorite = HOME / "carpeta_favorita.txt"
            if favorite.exists():
                path = favorite.read_text(encoding="utf-16").strip()
                if Path(path).is_dir() and sys.platform=="win32":
                    os.startfile(path)
                    return "Abriendo carpeta favorita.",3
            return "Configura primero la carpeta favorita desde Atajos.",3
        if name in ("explorador", "archivos"):
            if sys.platform=="win32":subprocess.Popen(["explorer.exe"])
            return "Abriendo Explorador.",3
        url=resolve_site(name)
        if url:
            if name=="spotify":open_spotify()
            else:webbrowser.open(url)
            return "Abriendo atajo "+name+".",3
        tab=next((x for x in load_tabs() if norm(x["name"])==norm(name)),None)
        if tab:
            if tab["url"]:
                webbrowser.open(tab["url"])
                return "Abriendo atajo "+name+".",3
            return "Esta pestaña aún no tiene enlace.",-1
        return "No conozco ese atajo. Crea una pestaña y asígnale un sitio.",-1

    event = re.match(r"^(?:agrega|anade|crea|programa|agenda|pon)\s+(?:un\s+)?(?:evento|cita|reunion|recordatorio)\s+(.+?)(?:\s+(?:en|a)\s+(?:mi\s+)?calendario)?$",t)
    if event:
        data=make_calendar_draft(event.group(1))
        if data is None:
            return "Indica fecha y hora, por ejemplo: reunión mañana a las 3 de la tarde.", 2
        return data[0],2

    if any(x in t for x in ("muestrame mi pc", "abre mi pc", "mostrar mi pc", "abre este equipo")):
        show_my_pc()
        return "Abriendo Este equipo.", 4

    # «abre Spotify» tiene que abrir la aplicacion, no solo cambiar de modulo.
    if t in ("abre spotify", "inicia spotify", "pon spotify"):
        open_spotify()
        return "Abriendo Spotify.", 0

    # Frases cortas habituales de voz: «accede a chat e pepe» ya se
    # canonizo arriba como «abre chatgpt» y entra en esta rama.
    selected = re.fullmatch(r"(?:muestra|muestrame|ve|ve a|abre|ir a|cambia a)\s+(?:mi\s+|el\s+|la\s+)?(?:pestana\s+|modulo\s+)?(.+)", t)
    if selected:
        target=selected.group(1)
        page=current_page_for(target)
        if page is not None:
            return "Mostrando "+target+".",page
        if target in ("explorador", "archivos", "carpeta", "explorador de archivos"):
            if sys.platform == "win32": subprocess.Popen(["explorer.exe"])
            return "Abriendo Explorador de archivos.",3
        if target in ("ajustes", "configuracion de windows"):
            open_settings()
            return "Abriendo configuración.",3
        url=resolve_site(target)
        if url:
            if target == "spotify":open_spotify()
            else:webbrowser.open(url)
            return "Abriendo "+target+".",3

    if t.startswith(("reproduce spotify", "reproducir spotify", "pon spotify", "inicia spotify")):
        open_spotify()
        # Only play after an actual Spotify session becomes current.
        for _ in range(3):
            detected,playing=status_spotify()
            if detected:
                if playing:return "Spotify ya está reproduciendo.",0
                return media_play(),0
            time.sleep(0.5)
        return "Spotify abierto. Elige una canción si todavía no se reproduce.",0

    if t.startswith(("reproduce musica", "pon musica", "continua musica", "reanuda musica")):
        detected,playing=status_spotify()
        if detected and playing:return "La música ya está reproduciéndose.",0
        return media_play(),0

    if t in ("siguiente cancion", "cancion siguiente", "siguiente") and sys.platform=="win32":
        import ctypes
        ctypes.windll.user32.keybd_event(0xB0,0,0,0)
        ctypes.windll.user32.keybd_event(0xB0,0,0x0002,0)
        return "Siguiente canción.",0

    if t in ("ayuda", "que puedes hacer", "comandos"):
        return "Puedo abrir Spotify, Mi PC, atajos, crear pestañas y preparar eventos.", -1

    return "No entendí la orden. Prueba: abre ChatGPT o crea pestaña Trabajo.",-1


def process_utterance(utterance: str, awaiting: bool) -> tuple[bool, bool]:
    spoken=norm(utterance)
    match=WAKE.search(spoken)
    if match:
        command=spoken[match.end():].strip(" ,.")
        if not command:
            notify("listening", "Te escucho. ¿Qué necesitas?")
            return True, True
    elif spoken in ("over","hover","jover","oye hover","oye jover","oye over"):
        notify("listening", "Te escucho. ¿Qué necesitas?")
        return True, True
    elif awaiting:
        command=spoken
    else:
        # Permite «abre chat pete over» cuando el reconocedor invierte
        # el orden. Solo en frases claramente imperativas y sitios conocidos.
        tail=TRAILING_WAKE.search(spoken)
        candidate=spoken[:tail.start()] if tail else ""
        canonical=canonical_command(candidate)
        if not (tail and re.match(r"^(?:abre|reproduce|muestra)\s+",canonical) and
                any(site in canonical for site in ("chatgpt","spotify","claude"))):
            return False, False
        command=candidate
    command=canonical_command(command)
    notify("thinking", "Entendido: " + command[:76])
    try:
        result,page=process_command(command)
        if page>=len(PAGE_NAMES):
            time.sleep(0.15)
        notify("ok",result,page)
        speak(result)
    except (OSError,ValueError,RuntimeError) as exc:
        notify("error","No se pudo completar la orden: "+str(exc)[:62])
    return True, False


def run_text_mode() -> None:
    print("HOVER VOZ 4.1 -- prueba sin micrófono. Escribe 'salir' para cerrar.")
    print("Ejemplos: oye hover abre chatgpt | oye hover crea pestaña trabajo para github")
    awaiting=False
    while True:
        try:raw=input("HOVER> ").strip()
        except (KeyboardInterrupt, EOFError):break
        if norm(raw) in ("salir", "exit", "quit"):break
        handled,awaiting=process_utterance(raw,awaiting)
        if not handled:print("(Di primero: Oye Hover)")


def run_microphone(model_path: Path, microphone: int | None = None) -> None:
    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer, SetLogLevel
    except ImportError as exc:
        raise SystemExit("Faltan dependencias. Ejecuta INSTALAR_VOZ_HOVER.bat") from exc
    if not model_path.is_dir():
        raise SystemExit("No se encontró el modelo Vosk en: "+str(model_path)+
                         "\nDescarga un modelo español desde https://alphacephei.com/vosk/models")
    SetLogLevel(-1)
    model=Model(str(model_path))
    info=sd.query_devices(microphone,"input")
    samplerate=int(info["default_samplerate"])
    rec=KaldiRecognizer(model,samplerate)
    rec.SetMaxAlternatives(3)
    audio_queue:queue.Queue[bytes]=queue.Queue(maxsize=80)
    deadline=0.0

    def callback(indata,frames,time_info,status):
        del frames,time_info
        if status:print("Micrófono:",status,file=sys.stderr)
        if _TTS_BUSY.is_set():return
        try:audio_queue.put_nowait(bytes(indata))
        except queue.Full:pass

    print("Oye HOVER - micrófono",info["name"],"| Ctrl+C para detener")
    notify("idle","Di: Oye Hover")
    with sd.RawInputStream(samplerate=samplerate,blocksize=4000,device=microphone,
                           dtype="int16",channels=1,callback=callback):
        while True:
            data=audio_queue.get()
            if not rec.AcceptWaveform(data):continue
            if _TTS_BUSY.is_set():
                rec.Reset()
                continue
            try:raw=best_vosk_result(json.loads(rec.Result()))
            except (ValueError,TypeError):continue
            if not raw:continue
            print("Reconocido:",raw)
            corrected=canonical_command(raw)
            if corrected!=norm(raw):print("Interpretado:",corrected)
            active=time.monotonic()<deadline
            handled,awaiting=process_utterance(raw,active)
            if handled:
                rec.Reset()
                while True:
                    try:audio_queue.get_nowait()
                    except queue.Empty:break
            if awaiting:deadline=time.monotonic()+9.0
            else:deadline=0.0


def run_whisper_microphone(microphone: int | None = None,
                           model_size: str = "base") -> None:
    """Transcripcion local con faster-whisper y segmentacion sencilla por voz.

    Captura mono int16. Si el microfono no acepta 16 kHz, remuestrea desde
    su frecuencia nativa a 16 kHz con numpy. No graba ni sube audio.
    """
    try:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel
        from collections import deque
    except ImportError as exc:
        raise SystemExit("Falta faster-whisper. Ejecuta INSTALAR_WHISPER_HOVER.bat") from exc
    if model_size not in ("tiny", "base", "small", "medium"):
        raise SystemExit("Modelo no admitido; usa tiny, base, small o medium")
    print("Cargando Whisper",model_size,"en CPU (int8). La primera vez descargara el modelo.",flush=True)
    whisper=WhisperModel(model_size,device="cpu",compute_type="int8")
    info=sd.query_devices(microphone,"input")
    samplerate=int(info["default_samplerate"])
    blocksize=max(256,int(samplerate*0.05))
    audio_queue:queue.Queue[bytes]=queue.Queue(maxsize=120)
    from collections import deque
    preroll=deque(maxlen=7)
    noise_floor=0.004
    speech=False
    chunks:list[bytes]=[]
    silent_duration=0.0
    speech_duration=0.0
    deadline=0.0

    def callback(indata,frames,time_info,status):
        del frames,time_info
        if status:print("Micrófono:",status,file=sys.stderr)
        if _TTS_BUSY.is_set():return
        try:audio_queue.put_nowait(bytes(indata))
        except queue.Full:pass

    print("Oye HOVER - Whisper",model_size,"| Micrófono",info["name"],"| Ctrl+C para detener")
    notify("idle","Di: Oye Hover")
    with sd.RawInputStream(samplerate=samplerate,blocksize=blocksize,device=microphone,
                           dtype="int16",channels=1,callback=callback):
        while True:
            raw=audio_queue.get()
            if _TTS_BUSY.is_set():
                speech=False;chunks=[];preroll.clear()
                continue
            pcm=np.frombuffer(raw,dtype=np.int16)
            rms=float(np.sqrt(np.mean((pcm.astype(np.float32)/32768.0)**2)))
            frame_secs=len(pcm)/float(samplerate)
            trigger=max(0.009,noise_floor*2.7)
            if not speech:
                if rms<trigger:
                    noise_floor=0.97*noise_floor+0.03*rms
                    preroll.append(raw)
                    continue
                speech=True
                chunks=list(preroll);preroll.clear()
                speech_duration=0.0;silent_duration=0.0
            chunks.append(raw)
            speech_duration+=frame_secs
            if rms<trigger*0.65:
                silent_duration+=frame_secs
            else:
                silent_duration=0.0
            if (silent_duration<0.80 and speech_duration<9.0):
                continue
            speech=False
            if speech_duration<0.38:
                chunks=[]
                continue
            pcm32=np.frombuffer(b"".join(chunks),dtype=np.int16).astype(np.float32)/32768.0
            chunks=[]
            if samplerate!=16000:
                desired=max(1,int(len(pcm32)*16000/samplerate))
                pcm32=np.interp(np.linspace(0,len(pcm32)-1,desired),
                                np.arange(len(pcm32)),pcm32).astype(np.float32)
            print("[asr] transcribiendo",flush=True)
            try:
                segments,_=whisper.transcribe(
                    pcm32,language="es",beam_size=4,
                    condition_on_previous_text=False,vad_filter=False,
                    initial_prompt=("Oye Hover. Abre ChatGPT. Abre Spotify. "
                                    "Abre Claude. Muéstrame mi PC. Crea una pestaña."))
                recognized=" ".join(seg.text.strip() for seg in segments).strip()
            except Exception as exc:
                print("Whisper no pudo transcribir:",exc,file=sys.stderr)
                continue
            # No reutilizar audio capturado mientras Whisper tardaba en decodificar.
            while True:
                try:audio_queue.get_nowait()
                except queue.Empty:break
            if not recognized:continue
            print("Reconocido:",recognized,flush=True)
            corrected=canonical_command(recognized)
            if corrected!=norm(recognized):print("Interpretado:",corrected,flush=True)
            active=time.monotonic()<deadline
            handled,awaiting=process_utterance(recognized,active)
            deadline=time.monotonic()+9.0 if awaiting else 0.0


def main() -> int:
    ap=argparse.ArgumentParser(description="HOVER - asistente offline para Windows")
    ap.add_argument("--texto",action="store_true",help="Probar comandos sin micrófono")
    ap.add_argument("--motor",choices=("vosk","whisper"),default="vosk",
                    help="Motor de reconocimiento local. Whisper suele reconocer mejor los nombres propios.")
    ap.add_argument("--tamano",choices=("tiny","base","small","medium"),default="base",
                    help="Tamano de Whisper. base recomendado en CPU; small mas preciso y pesado.")
    ap.add_argument("--modelo",default=str(Path(__file__).parent/"modelo-es"))
    ap.add_argument("--microfono",type=int,default=None)
    ap.add_argument("--listar-microfonos",action="store_true")
    ap.add_argument("--hablar",action="store_true",help="Responder en voz con SAPI local de Windows")
    args=ap.parse_args()
    global SPEAK_ENABLED
    SPEAK_ENABLED=args.hablar
    publish_tabs()
    if args.listar_microfonos:
        try:
            import sounddevice as sd
            print(sd.query_devices())
        except ImportError:print("Instala sounddevice primero.")
        return 0
    try:
        if args.texto:run_text_mode()
        elif args.motor=="whisper":run_whisper_microphone(args.microfono,args.tamano)
        else:run_microphone(Path(args.modelo),args.microfono)
    except KeyboardInterrupt:pass
    finally:notify("idle","Asistente de voz detenido")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

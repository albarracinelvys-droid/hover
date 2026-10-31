#!/usr/bin/env python3
"""HOVER voz v4.3: reconocimiento offline Vosk y acciones locales limitadas.

Activación: «Oye Hover» / «Oye Jover». Sin API externa ni captura permanente
almacenada: los fragmentos del micrófono se procesan en memoria.

No ejecuta órdenes arbitrarias del sistema. Los eventos .ics requieren confirmar
la importación en la aplicación de calendario; no se añaden silenciosamente.

Prueba sin micrófono/modelo: python Asistente_Voz_HOVER_v4_3.py --texto
"""
from __future__ import annotations

import argparse
import json
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
    r"^(?:(?:oye|hey|ei|hola|ok)\s+)(?:hover|jover|over|hober|hoover|ober|llover|yover)\b",
    re.I,
)

_TTS_BUSY = threading.Event()
_PENDING_MOVE: tuple[Path, Path, float] | None = None
F8_ONLY = False


# El modelo pequeno suele transcribir los nombres ingleses de manera fonetica.
# Son ALIAS de comandos conocidos: no permite ejecutar ordenes arbitrarias.
SITE_PHONETICS = {
    "chatgpt": [
        "chat gpt", "chat ge pe te", "chat ge pete", "chat gepete",
        "chat e pepe", "chat e pete", "chat pete", "chat jep", "chat jepe",
        "chat e pretende", "chat e pretendi", "chat e pretendo", "chat gp",
        "chat gep", "chat ye pe te", "cati piti", "cati peti", "cati petit", "chat yipiti",
        "chati piti", "chat gepiti", "chat yi pi ti", "chat piti", "chat g p t",
        "chat e p t", "chat chipe te", "chat e pepe te", "calle petty", "calle peti", "calle petti", "calle piti", "cha tip tip", "chat ipiti", "chati peti", "chati petit", "chati peti", "chat tipi ti",
    ],
    "spotify": ["espotifai", "espotify", "spotifai", "espotifay", "spotifay", "es potify", "espotifay"],
    "claude": ["clau", "claud", "claudio"],
}


def canonical_command(value: str) -> str:
    t = norm(value).strip(" .,!?¿¡")
    t = re.sub(r"^a\s+brecha\s+", "abre ", t)
    t = re.sub(r"^(?:habre|abrir|abra)\s+", "abre ", t)
    # Proteger las partes informativas de eventos y nombres de pestana:
    # solo se corrigen los nombres de sitios/comandos conocidos.
    for name, alternatives in SITE_PHONETICS.items():
        for alias in sorted(alternatives, key=len, reverse=True):
            t = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", name, t)
    t = re.sub(r"^(?:accede|acceda|accede|acces|aces|acede|acedea|acceso|entra|ingresa|visita)\s+(?:a\s+|al\s+)?", "abre ", t)
    t = re.sub(r"^(?:alli se ha|alise a|alise ha|dale a)\s+(chatgpt|spotify|claude)\b", r"abre \1",t)
    t = re.sub(r"^(?:abrir|habre|abra)\s+", "abre ", t)
    t = re.sub(r"^(?:muestreme|muestrame)\s+", "muestra ", t)
    # Whisper a veces interpreta "reproduce" como "reproces", "reprodus",
    # "reproduces" o "reproduzca". Corregimos SOLO el verbo inicial.
    t = re.sub(r"^(?:reproces|reproses|reprodus|reprodusce|reproduces|reproduzca|reproducir|reproduceme|reprodusir)\b", "reproduce", t)
    t = re.sub(r"^(?:ponme|ponte|coloca|reproduce la)\s+(?=musica|spotify)", "pon ", t)
    return t


def transcript_score(raw: str) -> float:
    """Prioriza alternativas con wake word y una accion conocida; no fabrica acciones."""
    spoken=norm(raw)
    canon=canonical_command(spoken)
    score = 0.0
    if WAKE.match(spoken): score+=5.0
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


def open_known_site(site: str, url: str) -> str:
    """Pide abrir una URL permitida; nunca informa que se cargó sin comprobarlo.

    webbrowser.open() devuelve si pudo lanzar el navegador, no garantiza que
    la página haya terminado de cargar. Mantener el feedback honesto.
    """
    if not valid_url(url):
        return "Dirección no válida; no abrí ninguna página."
    print(f"[accion] abrir navegador: {site} -> {url}", flush=True)
    try:
        started = bool(webbrowser.open(url, new=2))
        if not started and sys.platform == "win32":
            # Fallback al manejador de URL predeterminado de Windows.
            try:
                os.startfile(url)
                started = True
                print("[accion] se utilizó el manejador de Windows", flush=True)
            except OSError as exc:
                print(f"[accion] fallo de Windows: {exc}", flush=True)
        print(f"[accion] navegador aceptó orden: {started}", flush=True)
    except (OSError, webbrowser.Error) as exc:
        return f"No pude abrir {site}: {str(exc)[:90]}"
    return (f"Envié la orden de abrir {site} al navegador." if started
            else f"No pude iniciar el navegador para {site}. Revisa tu navegador predeterminado.")


def close_foreground_chatgpt_tab() -> str:
    """Cierra UNA pestaña SOLO si ChatGPT está activa en un navegador real.

    La interfaz de Windows no permite identificar de manera fiable una pestaña
    en segundo plano sin una extensión de navegador. Por eso nunca utilizamos
    Ctrl+W sobre una app cualquiera ni afirmamos cerrar 'la última' a ciegas.
    """
    if sys.platform != "win32":
        return "Cerrar pestañas desde HOVER requiere Windows."
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    # Win64: las funciones HWND deben declararse para NO truncar punteros.
    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    u32.GetWindowTextW.restype = ctypes.c_int
    u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    u32.GetWindowThreadProcessId.restype = wintypes.DWORD
    u32.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t)
    u32.keybd_event.restype = None
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return "No encuentro una ventana activa. Selecciona ChatGPT y vuelve a pedir cerrar."
    title_buffer = ctypes.create_unicode_buffer(1024)
    u32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
    title = norm(title_buffer.value)
    if "chatgpt" not in title and "chat gpt" not in title:
        return "No cerré nada: activa la pestaña de ChatGPT en el navegador y repite la orden."

    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return "No pude identificar el navegador. No cerré ninguna pestaña."
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel = ctypes.windll.kernel32
    # Definir tipos para preservar punteros de 64 bits en Windows.
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                   wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return "No pude verificar la aplicación. No cerré ninguna pestaña."
    try:
        executable = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(executable))
        if not kernel.QueryFullProcessImageNameW(handle, 0, executable, ctypes.byref(size)):
            return "No pude verificar el navegador. No cerré ninguna pestaña."
        exe = Path(executable.value).name.casefold()
    finally:
        kernel.CloseHandle(handle)
    supported = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
                 "opera.exe", "vivaldi.exe", "chromium.exe"}
    if exe not in supported:
        return "Esa ventana no es un navegador compatible. No la cerré."

    # Ctrl+W sobre la ventana verificada en primer plano. No tocamos procesos
    # en segundo plano ni otras pestañas cuyo título/URL no podemos comprobar.
    VK_CONTROL, VK_W = 0x11, 0x57
    KEYEVENTF_KEYUP = 0x0002
    u32.keybd_event(VK_CONTROL, 0, 0, 0)
    u32.keybd_event(VK_W, 0, 0, 0)
    u32.keybd_event(VK_W, 0, KEYEVENTF_KEYUP, 0)
    u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return "Solicité cerrar la pestaña activa de ChatGPT."


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


def play_spotify_targeted() -> str | None:
    """Controla SOLO Spotify por GSMTC (WinRT), nunca Chrome u otra sesión.

    None = PyWinRT no instalado/no disponible. Esta función no necesita red
    ni tokens de Spotify. Requiere que la app exponga una sesión multimedia.
    """
    try:
        import asyncio
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
    except ImportError:
        return None

    async def execute() -> str:
        manager = await SessionManager.request_async()
        candidates = [session for session in manager.get_sessions()
                      if "spotify" in str(session.source_app_user_model_id).casefold()]
        if not candidates:
            return "missing_session"
        session = candidates[0]
        try:
            if session.get_playback_info().playback_status == PlaybackStatus.PLAYING:
                return "already_playing"
            success = bool(await session.try_play_async())
            return "started" if success else "rejected"
        except Exception:
            return "rejected"
    try:
        return asyncio.run(execute())
    except Exception as exc:
        print("[accion] Spotify WinRT no disponible:", type(exc).__name__, flush=True)
        return None


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


def capture_screen() -> str:
    """Abre la herramienta de recorte de Windows; no guarda ni publica capturas."""
    if sys.platform != "win32":
        return "La captura de pantalla requiere Windows."
    import ctypes
    u32 = ctypes.windll.user32
    # Win + Shift + S abre el selector nativo de regiones.
    for vk in (0x5B, 0x10, 0x53):
        u32.keybd_event(vk, 0, 0, 0)
    for vk in (0x53, 0x10, 0x5B):
        u32.keybd_event(vk, 0, 2, 0)
    return "Selecciona la región de la pantalla que deseas capturar."


def favorite_folder() -> Path | None:
    path = HOME / "carpeta_favorita.txt"
    if not path.is_file():
        return None
    try:
        folder = Path(path.read_text(encoding="utf-16").strip("\ufeff\0 "))
        return folder if folder.is_dir() else None
    except (OSError, UnicodeError):
        return None


def downloads_folder() -> Path:
    # Ubicación habitual; no presupone acceso a archivos de otros usuarios.
    return Path.home() / "Downloads"


def get_latest_download() -> Path | None:
    directory = downloads_folder()
    if not directory.is_dir():
        return None
    candidates = []
    for p in directory.iterdir():
        try:
            if p.is_file() and not p.is_symlink() and p.suffix.casefold() not in (
                ".part", ".crdownload", ".tmp", ".download"):
                candidates.append(p)
        except OSError:
            continue
    return max(candidates, key=lambda p:p.stat().st_mtime, default=None)


def prepare_move() -> str:
    global _PENDING_MOVE
    target_folder = favorite_folder()
    if target_folder is None:
        return "Configura primero tu carpeta favorita en el módulo Atajos de HOVER."
    selected = get_latest_download()
    if selected is None:
        return "No encuentro archivos terminados en la carpeta Descargas."
    if selected.parent.resolve() == target_folder.resolve():
        return "El archivo ya está en esa carpeta."
    _PENDING_MOVE = (selected, target_folder, time.monotonic()+20.0)
    return (f"¿Confirmas mover {selected.name} a {target_folder.name}? "
            "Di confirmar o cancelar en los próximos veinte segundos.")


def finish_move(confirm: bool) -> str:
    global _PENDING_MOVE
    pending, _PENDING_MOVE = _PENDING_MOVE, None
    if pending is None or pending[2] < time.monotonic():
        return "No hay movimientos pendientes."
    if not confirm:
        return "Movimiento cancelado."
    source, dest_folder, _ = pending
    if not source.is_file() or source.is_symlink() or not dest_folder.is_dir():
        return "El archivo o carpeta cambiaron; no se realizó el movimiento."
    destination = dest_folder / source.name
    if destination.exists():
        destination = dest_folder / f"{source.stem}_{uuid.uuid4().hex[:6]}{source.suffix}"
    shutil.move(str(source), str(destination))
    return f"Archivo {source.name} movido a {dest_folder.name}."


def command_is_move_confirmation(command: str) -> bool:
    t = norm(command)
    return t in ("confirmar", "confirmo", "si confirma", "si confirmar", "si confirmo",
                 "cancela", "cancelar", "no cancelar", "no cancela")


def process_command(command: str) -> tuple[str, int]:
    """Returns (feedback, optional HOVER page). No shell execution from speech."""
    t = canonical_command(command)
    if not t:
        return "Te escucho. Dime qué necesitas.", -1

    if command_is_move_confirmation(t):
        return finish_move(t.startswith(("confirma", "confirmo", "si"))), 3

    # El verbo "cierra" nunca debe terminar en el enrutador de abrir páginas.
    if re.match(r"^(?:cierra|cerrar|cierra la|cierra el)\b", t):
        if re.search(r"\b(?:chatgpt|chat gpt)\b", t) and re.search(r"\b(?:pestana|tab|ventana|chatgpt)\b", t):
            return close_foreground_chatgpt_tab(), -1
        return ("Para evitar cerrar otra aplicación, solo puedo cerrar la pestaña activa "
                "de ChatGPT cuando la tengas al frente. No cerré nada."), -1

    if re.search(r"\b(?:mueve|mover|traslada|lleva|enviar|envia)\b", t) and \
       re.search(r"\bultimo archivo\b", t) and \
       re.search(r"\bdescargas\b", t):
        return prepare_move(), 3

    if re.match(r"^(?:toma|tomar|haz|hacer|saca|sacar|realiza|realizar|abrir)\s+(?:una\s+)?(?:captura|pantallazo|screenshot)\b", t) or \
       t in ("captura de pantalla", "capturar pantalla", "captura pantalla", "pantallazo"):
        return capture_screen(), 3

    if re.match(r"^(?:muestra|abre|ensename|quiero ver|mostrar)\s+(?:mi\s+)?(?:pc|computador|ordenador|este equipo)\b", t) and \
       not re.fullmatch(r"(?:muestra|abre)\s+(?:equipo|hardware)",t):
        show_my_pc()
        return "Abriendo Este equipo.", 4

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
                path = favorite.read_text(encoding="utf-16").strip("\ufeff\0 ")
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
            else:return open_known_site(name,url),3
            return "Solicité abrir Spotify.",3
        tab=next((x for x in load_tabs() if norm(x["name"])==norm(name)),None)
        if tab:
            if tab["url"]:
                return open_known_site(name,tab["url"]),3
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
    if t in ("abre spotify", "inicia spotify"):
        return ("Solicité abrir Spotify." if open_spotify() else "No pude abrir Spotify."), 0

    # Reconocer "reproces Spotify" via canonical_command. No cambiar de página
    # como única respuesta; abrir app y reproducir solo si hay sesión de Spotify.
    if re.match(r"^(?:reproduce|pon|reanuda|continua|inicia)\s+(?:(?:la|una)\s+)?(?:musica\s+(?:de|en)\s+)?spotify\b", t):
        launched = open_spotify()
        if not launched:
            return "No pude abrir Spotify. Comprueba que esté instalado o usa Spotify web.", 0
        for _ in range(5):
            # Preferir reproducción dirigida a Spotify (no tecla global).
            direct = play_spotify_targeted()
            if direct == "already_playing":
                return "Spotify ya está reproduciendo.", 0
            if direct == "started":
                return "Solicité reproducir Spotify a su sesión multimedia.", 0
            if direct == "rejected":
                return "Spotify rechazó la orden de reproducción. Selecciona una canción y repite.", 0
            if direct is None:
                # PyWinRT no está en este entorno: comprobar el puente legado.
                detected, playing = status_spotify()
                if detected:
                    if playing:
                        return "Spotify ya está reproduciendo.", 0
                    return media_play(), 0
            time.sleep(0.35)
        return ("Spotify se abrió, pero todavía no hay una sesión reproducible. "
                "Reproduce una canción una vez y vuelve a intentarlo."), 0

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
            if target == "spotify":
                return ("Solicité abrir Spotify." if open_spotify() else "No pude abrir Spotify."), 0
            return open_known_site(target,url),3

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

    return "Todavía no tengo esa acción. Prueba abrir ChatGPT, Spotify, hacer una captura, o mostrar Equipo.",-1


def process_utterance(utterance: str, awaiting: bool) -> tuple[bool, bool]:
    """Las órdenes solo se admiten tras una activación al comienzo de la frase.

    Una clase, video o conversación de fondo que mencione «oye hover» a mitad
    de una oración no puede disparar acciones. F8 habilita una ventana corta
    de reconocimiento incluso sin decir «Oye Hover».
    """
    spoken = norm(utterance).strip(" .,!?¿¡")
    if not spoken:
        return False, awaiting
    match = WAKE.match(spoken)
    if match:
        command = spoken[match.end():].strip(" ,.")
        if not command:
            notify("listening", "Te escucho. Dime una orden corta.")
            return True, True
    elif spoken in ("hover", "jover", "oye hover", "oye jover", "oye over"):
        notify("listening", "Te escucho. Dime una orden corta.")
        return True, True
    elif awaiting:
        command = spoken
    else:
        return False, False

    command = canonical_command(command)
    if len(command.split()) > 22 or len(command) > 160:
        notify("idle", "Escuché una frase larga; no ejecutaré acciones del entorno.")
        return True, False
    if not re.search(r"\b(?:abre|muestra|crea|agrega|anade|configura|reproduce|pon|"
                     r"inicia|ejecuta|accede|toma|haz|saca|realiza|captura|"
                     r"mueve|mover|traslada|lleva|envia|confirmar|confirmo|"
                     r"cancelar|cancela|cierra|cerrar|siguiente|ayuda|que)\b",command):
        notify("idle", "No identifiqué una orden; vuelve a decir Oye Hover.")
        return True, False
    notify("thinking", "Entendido: " + command[:76])
    try:
        result, page = process_command(command)
        if page >= len(PAGE_NAMES):
            time.sleep(0.15)
        refused = result.startswith((
            "No pude", "No cerré", "No encuentro", "No reconozco",
            "Todavía no", "Para evitar", "No conozco", "No existe",
            "No se pudo", "Esa ventana no", "No hay movimientos"))
        notify("error" if refused else "ok", result, page)
        speak(result)
    except (OSError, ValueError, RuntimeError) as exc:
        notify("error", "No se pudo completar la orden: " + str(exc)[:62])
    # Permitir una respuesta de confirmar/cancelar sin repetir la activación.
    return True, _PENDING_MOVE is not None


def run_text_mode() -> None:
    print("HOVER VOZ 4.3 -- prueba sin micrófono. Escribe 'salir' para cerrar.")
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
            active=time.monotonic()<deadline
            handled,awaiting=process_utterance(raw,active)
            if handled:
                print("Reconocido:",raw)
                corrected=canonical_command(raw)
                if corrected!=norm(raw):print("Interpretado:",corrected)
            if handled:
                rec.Reset()
                while True:
                    try:audio_queue.get_nowait()
                    except queue.Empty:break
            if awaiting:deadline=time.monotonic()+9.0
            else:deadline=0.0


def run_whisper_microphone(microphone: int | None = None,
                           model_size: str = "small", f8_only: bool = False) -> None:
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
    f8_was_down=False
    f8_deadline=0.0

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
            # F8 sólo activa HOVER, no roba el teclado a la app activa.
            if sys.platform == "win32":
                import ctypes
                pressed=bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)
                if pressed and not f8_was_down:
                    f8_deadline=time.monotonic()+10.0
                    notify("listening", "F8: dime tu orden.")
                f8_was_down=pressed
            if f8_only and time.monotonic()>f8_deadline:
                speech=False;chunks=[];preroll.clear()
                continue
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
                    pcm32,language="es",beam_size=5,temperature=0,
                    condition_on_previous_text=False,vad_filter=False,
                    no_speech_threshold=0.6,
                    initial_prompt=("Nombres propios: HOVER, ChatGPT, Claude, Spotify, GitHub."))
                recognized=" ".join(seg.text.strip() for seg in segments).strip()
            except Exception as exc:
                print("Whisper no pudo transcribir:",exc,file=sys.stderr)
                continue
            # No reutilizar audio capturado mientras Whisper tardaba en decodificar.
            while True:
                try:audio_queue.get_nowait()
                except queue.Empty:break
            if not recognized:continue
            active=time.monotonic()<deadline or time.monotonic()<f8_deadline
            handled,awaiting=process_utterance(recognized,active)
            if handled:
                print("Reconocido:",recognized,flush=True)
                corrected=canonical_command(recognized)
                if corrected!=norm(recognized):print("Interpretado:",corrected,flush=True)
            deadline=time.monotonic()+9.0 if awaiting else 0.0
            if f8_only and handled: f8_deadline=0.0


def main() -> int:
    ap=argparse.ArgumentParser(description="HOVER - asistente offline para Windows")
    ap.add_argument("--texto",action="store_true",help="Probar comandos sin micrófono")
    ap.add_argument("--motor",choices=("vosk","whisper"),default="whisper",
                    help="Motor de reconocimiento local. Whisper suele reconocer mejor los nombres propios.")
    ap.add_argument("--tamano",choices=("tiny","base","small","medium"),default="small",
                    help="Tamano de Whisper. base recomendado en CPU; small mas preciso y pesado.")
    ap.add_argument("--modelo",default=str(Path(__file__).parent/"modelo-es"))
    ap.add_argument("--solo-f8",action="store_true",help="No procesa voz de fondo. Pulsa F8 y luego di la orden.")
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
        elif args.motor=="whisper":run_whisper_microphone(args.microfono,args.tamano,args.solo_f8)
        else:run_microphone(Path(args.modelo),args.microfono)
    except KeyboardInterrupt:pass
    finally:notify("idle","Asistente de voz detenido")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

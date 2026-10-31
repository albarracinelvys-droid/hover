"""Puente multimedia local para HOVER v3.9.2.

Lee las sesiones multimedia publicadas por Windows (GSMTC) y escribe solo
metadatos no sensibles en %TEMP%/WindhawkIslandPremium/status.txt.
Recibe los comandos de reproducción del mod a través de un archivo local.
No usa Spotify Web API, no necesita OAuth y no se conecta a servicios externos.

Requisitos: Windows 10/11, Python 3.11+, paquete PyWinRT.
"""

from __future__ import annotations

import asyncio
import os
import hashlib
import tempfile
import time
from pathlib import Path

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
except ImportError:
    MediaManager = None
    PlaybackStatus = None

BASE = Path(tempfile.gettempdir()) / "WindhawkIslandPremium"
BASE.mkdir(parents=True, exist_ok=True)
STATUS = BASE / "status.txt"
COMMAND = BASE / "command.txt"

# La miniatura es opcional; si falta el paquete, HOVER dibuja un visualizador
# de barras animadas. El portapapeles y los metadatos siguen funcionando.
try:
    from winrt.windows.storage.streams import InputStreamOptions
except ImportError:
    InputStreamOptions = None

async def cover_from_media(media) -> str:
    """Devuelve el nombre local de una carátula que Windows suministra.

    No descarga imágenes por Internet ni usa credenciales de Spotify.
    """
    if InputStreamOptions is None or media is None:
        return ""
    try:
        reference = media.thumbnail
        if reference is None:
            return ""
        stream = await reference.open_read_async()
        size = min(int(stream.size), 524288)
        if size < 40:
            return ""
        input_stream = stream.get_input_stream_at(0)
        buf = bytearray(size)
        result = await input_stream.read_async(buf, size, InputStreamOptions.NONE)
        # PyWinRT returns an IBuffer implementing the buffer protocol. Its
        # length indicates the actual number of bytes read.
        raw = bytes(memoryview(result))
        if len(raw) < 40:
            return ""
        # PyWinRT y GDI+ aceptan PNG/JPG de proveedores SMTC. Otros formatos
        # se descartan para no entregar un archivo que no se pueda pintar.
        if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or
                raw.startswith(b"\xff\xd8\xff")):
            return ""
        digest = hashlib.sha256(raw).hexdigest()[:16]
        ext = ".png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else ".jpg"
        name = "cover_" + digest + ext
        target = BASE / name
        if not target.exists():
            tmp = BASE / ("." + name + ".new")
            tmp.write_bytes(raw)
            os.replace(tmp, target)
        return name
    except Exception:
        return ""



def clean(value: object, limit: int = 240) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("=", " ").strip()[:limit]


def write_state(fields: dict[str, object]) -> None:
    text = "\n".join(f"{key}={clean(val)}" for key, val in fields.items()) + "\n"
    staging = BASE / "status.new"
    staging.write_text(text, encoding="utf-8")
    os.replace(staging, STATUS)


def choose_session(manager):
    """Prefer Spotify explicitly, even when Chrome has a media session.

    A Spotify-paused track should still display its title and artwork; the
    previous system-global heuristic could select an unrelated browser.
    """
    sessions=list(manager.get_sessions())
    spotify=next((x for x in sessions
                  if "spotify" in str(x.source_app_user_model_id).casefold()),None)
    if spotify is not None:
        return spotify,True
    current=manager.get_current_session()
    if current is not None:
        return current,False
    for item in sessions:
        return item,False
    return None,False


def friendly_source(app_id: object) -> str:
    name = str(app_id or "")
    lower = name.casefold()
    for fragment, label in (
        ("spotify", "Spotify"), ("chrome", "Google Chrome"),
        ("msedge", "Microsoft Edge"), ("firefox", "Firefox"),
        ("vlc", "VLC"), ("music", "Reproductor de musica"),
    ):
        if fragment in lower:
            return label
    return clean(name or "Reproductor de Windows", 80)


def parse_mode(info) -> tuple[bool, bool]:
    shuffle = False
    repeat = False
    try:
        shuffle = bool(info.is_shuffle_active)
    except (AttributeError, ValueError):
        pass
    try:
        rep = info.auto_repeat_mode
        repeat = "none" not in str(rep).casefold() and rep is not None
    except (AttributeError, ValueError):
        pass
    return shuffle, repeat


def progress_fraction(session) -> float:
    try:
        timeline = session.get_timeline_properties()
        # PyWinRT representa las duraciones WinRT como timedelta.
        end = timeline.end_time.total_seconds()
        start = timeline.start_time.total_seconds()
        pos = timeline.position.total_seconds()
        if end > start:
            return max(0.0, min(1.0, (pos - start) / (end - start)))
    except (AttributeError, ValueError, ZeroDivisionError):
        pass
    return -1.0


async def apply_command(session, command: str) -> None:
    """Only target the selected media session; no global key toggles."""
    if session is None:
        return
    try:
        if command=="play":
            info=session.get_playback_info()
            if info.playback_status==PlaybackStatus.PLAYING:
                await session.try_pause_async()
            else:
                await session.try_play_async()
        elif command=="prev":
            await session.try_skip_previous_async()
        elif command=="next":
            await session.try_skip_next_async()
        elif command=="shuffle":
            info=session.get_playback_info()
            try:
                await session.try_change_shuffle_active_async(
                    not bool(info.is_shuffle_active))
            except AttributeError:
                pass
        elif command=="repeat":
            from winrt.windows.media import MediaPlaybackAutoRepeatMode
            current=session.get_playback_info().auto_repeat_mode
            target=(MediaPlaybackAutoRepeatMode.NONE
                    if current!=MediaPlaybackAutoRepeatMode.NONE
                    else MediaPlaybackAutoRepeatMode.LIST)
            await session.try_change_auto_repeat_mode_async(target)
    except Exception as exc:
        print("[media] El reproductor rechazó:",command,type(exc).__name__,
              flush=True)


async def run(stop_event=None) -> None:
    print("Isla Dinamica Premium - Puente multimedia local")
    print("Leyendo sesiones de Windows; Ctrl+C para cerrar.")
    print("Estado:", STATUS)
    last_command = ""
    last_art_key = None
    last_art_name = ""
    last_art_attempt = 0.0
    manager = None
    # The producer can be the Windhawk mod or a direct voice command.
    # Commands must be monotonically versioned to prevent replay.
    try:
        COMMAND.unlink(missing_ok=True)
    except OSError:
        pass

    while stop_event is None or not stop_event.is_set():
        try:
            if manager is None:
                manager = await MediaManager.request_async()
            session, spotify = choose_session(manager)
            if COMMAND.exists():
                try:
                    raw = COMMAND.read_text(encoding="ascii").strip()
                    if raw and raw != last_command:
                        last_command = raw
                        action = raw.partition(":")[2]
                        await apply_command(session, action)
                except (OSError, UnicodeError):
                    pass

            data: dict[str, object] = dict(
                spotify=int(spotify), playing=0, shuffle=0, repeat=0,
                title="", artist="", source="", progress=-1, artwork="",
            )
            if session is not None:
                try:
                    media = await session.try_get_media_properties_async()
                    info = session.get_playback_info()
                    is_playing = info.playback_status == PlaybackStatus.PLAYING
                    shuffle, repeat = parse_mode(info)
                    art_key=(str(session.source_app_user_model_id),
                             str(media.title), str(media.artist))
                    if art_key!=last_art_key or (
                            not last_art_name and
                            time.monotonic()-last_art_attempt>=5.0):
                        last_art_key=art_key
                        last_art_attempt=time.monotonic()
                        last_art_name=await cover_from_media(media)
                    data.update(
                        playing=int(is_playing),
                        shuffle=int(shuffle),
                        repeat=int(repeat),
                        title=clean(media.title),
                        artist=clean(media.artist),
                        source=friendly_source(session.source_app_user_model_id),
                        progress=f"{progress_fraction(session):.4f}",
                        artwork=last_art_name,
                    )
                except Exception as exc:
                    print("No se pudo leer esta sesion:", type(exc).__name__)
            if session is None:
                last_art_key=None
                last_art_name=""
            write_state(data)
        except Exception as exc:
            print("No se pudo consultar Windows Media:", type(exc).__name__, str(exc)[:120])
            manager = None
        await asyncio.sleep(0.7)


_THREAD_LOCK = __import__("threading").Lock()
_STARTED = False

def start_background(stop_event) -> None:
    """Start the media bridge from HOVER voice, no extra .bat needed."""
    global _STARTED
    if MediaManager is None:
        print("[media] Falta PyWinRT. Instala requirements.txt para mostrar "
              "la portada y controlar Spotify desde la isla.",flush=True)
        return
    with _THREAD_LOCK:
        if _STARTED:
            return
        _STARTED=True

    def worker():
        global _STARTED
        try:
            asyncio.run(run(stop_event))
        except Exception as exc:
            print("[media] Error en el puente:",type(exc).__name__,flush=True)
        finally:
            _STARTED=False
    import threading
    threading.Thread(target=worker,daemon=True,name="hover-media-bridge").start()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Puente detenido.")

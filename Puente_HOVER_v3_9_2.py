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
from pathlib import Path

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
except ImportError as exc:
    raise SystemExit(
        "Falta PyWinRT. Ejecuta INSTALAR_PUENTE_HOVER.bat primero."
    ) from exc

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
        raw = bytes(result)
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
    """Primero el reproductor realmente activo, no Spotify pausado.

    Algunas apps publican varias sesiones, por ejemplo Spotify pausado y
    Chrome reproduciendo: la priorización anterior elegía Spotify igualmente.
    """
    sessions = list(manager.get_sessions())
    current = manager.get_current_session()

    def is_playing(session) -> bool:
        try:
            return session.get_playback_info().playback_status == PlaybackStatus.PLAYING
        except Exception:
            return False

    # Usamos la sesion activa del sistema si efectivamente esta reproduciendo.
    if current is not None and is_playing(current):
        selected = current
    else:
        selected = next((session for session in sessions if is_playing(session)), None)
        if selected is None:
            selected = current if current is not None else next(iter(sessions), None)

    if selected is None:
        return None, False
    spotify = "spotify" in str(selected.source_app_user_model_id).casefold()
    return selected, spotify


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
    if session is None:
        return
    try:
        if command == "play":
            await session.try_toggle_play_pause_async()
        elif command == "prev":
            await session.try_skip_previous_async()
        elif command == "next":
            await session.try_skip_next_async()
        elif command == "shuffle":
            info = session.get_playback_info()
            try:
                active = bool(info.is_shuffle_active)
                await session.try_change_shuffle_active_async(not active)
            except AttributeError:
                pass
        elif command == "repeat":
            # Solo se muestra/cambia cuando Windows publica esa propiedad.
            from winrt.windows.media import MediaPlaybackAutoRepeatMode
            info = session.get_playback_info()
            current = info.auto_repeat_mode
            target = (
                MediaPlaybackAutoRepeatMode.NONE
                if current != MediaPlaybackAutoRepeatMode.NONE
                else MediaPlaybackAutoRepeatMode.LIST
            )
            await session.try_change_auto_repeat_mode_async(target)
    except Exception as exc:  # Algunas apps no admiten todos los comandos GSMTC.
        print("Comando no admitido por el reproductor:", command, type(exc).__name__)


async def run() -> None:
    print("Isla Dinamica Premium - Puente multimedia local")
    print("Leyendo sesiones de Windows; Ctrl+C para cerrar.")
    print("Estado:", STATUS)
    last_command = ""
    last_art_key = None
    last_art_name = ""
    manager = None
    try:
        COMMAND.unlink(missing_ok=True)  # Evitar ejecutar comandos antiguos tras reiniciar.
    except OSError:
        pass

    while True:
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
                    if art_key!=last_art_key:
                        last_art_key=art_key
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


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Puente detenido.")

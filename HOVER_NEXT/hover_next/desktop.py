"""Safe, direct Windows and Google shortcuts for HOVER.

No arbitrary programs or shell commands are generated from speech.
Microsoft Word requires local Word + optional pywin32.
Google services open in the default browser, using the user's existing session.
"""
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

GOOGLE_URLS: dict[str, str] = {
    "google_home": "https://www.google.com/",
    "google_drive": "https://drive.google.com/drive/u/0/my-drive",
    "google_docs": "https://docs.google.com/",
    "google_docs_new": "https://docs.google.com/create",
    "google_sheets": "https://sheets.google.com/",
    "google_sheets_new": "https://sheets.google.com/create",
    "google_slides": "https://slides.google.com/",
    "google_slides_new": "https://slides.google.com/create",
    "google_calendar": "https://calendar.google.com/calendar/u/0/r",
    "google_calendar_new": "https://calendar.google.com/calendar/u/0/r/eventedit",
    "google_gmail": "https://mail.google.com/mail/u/0/#inbox",
    "google_gmail_compose": "https://mail.google.com/mail/u/0/#compose",
    "google_maps": "https://www.google.com/maps",
    "google_meet": "https://meet.google.com/",
    "google_keep": "https://keep.google.com/",
    "google_youtube": "https://www.youtube.com/",
    "google_photos": "https://photos.google.com/",
    "google_translate": "https://translate.google.com/",
}
DOCUMENT_TYPES = {".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".csv", ".odt", ".ods", ".odp"}

SITE_URLS: dict[str,str] = {
    "github": "https://github.com/",
    "whatsapp": "https://web.whatsapp.com/",
    "google_translate": "https://translate.google.com/",
    "outlook": "https://outlook.live.com/mail/",
    "onedrive": "https://onedrive.live.com/",
    "discord": "https://discord.com/app",
    "linkedin": "https://www.linkedin.com/",
    "notion": "https://www.notion.so/",
    "canva": "https://www.canva.com/",
    "vercel": "https://vercel.com/dashboard",
    "gemini": "https://gemini.google.com/app",
    "perplexity": "https://www.perplexity.ai/",
    "stackoverflow": "https://stackoverflow.com/",
}

def open_site_shortcut(site: str) -> str:
    url = SITE_URLS.get(site)
    if url is None:
        raise ActionUnavailable("Destino web no autorizado.")
    if not webbrowser.open_new_tab(url):
        raise ActionUnavailable(f"El navegador no aceptó la solicitud para {site}.")
    return f"Abriendo {site} en tu navegador."



class ActionUnavailable(RuntimeError):
    pass


def search_google(query: str) -> str:
    """Search safely in the default browser. No inferred query from noise."""
    from urllib.parse import quote_plus
    q = " ".join(str(query).split())
    if not 2 <= len(q) <= 180:
        raise ActionUnavailable("La busqueda necesita un texto claro.")
    url = "https://www.google.com/search?q=" + quote_plus(q, safe="")
    if not webbrowser.open_new_tab(url):
        raise ActionUnavailable("No pude abrir los resultados de Google.")
    return f"Buscando en Google: {q}"


def translate_google(text: str, target: str = "en") -> str:
    """Open Google Translate with the recognized text and chosen language.

    No local translation is fabricated. The user sees the result on Google.
    """
    from urllib.parse import urlencode
    accepted = {"en","es","fr","de","pt","it","ja","zh-CN","ko","ru"}
    if target not in accepted:
        raise ActionUnavailable("Idioma de traducción no disponible.")
    source = " ".join(str(text).split())
    if len(source) > 180:
        raise ActionUnavailable("La frase para traducir es demasiado larga.")
    if source:
        url = "https://translate.google.com/?" + urlencode(
            {"sl":"auto", "tl":target, "text":source, "op":"translate"})
    else:
        url = "https://translate.google.com/?" + urlencode({"sl":"auto","tl":target})
    if not webbrowser.open_new_tab(url):
        raise ActionUnavailable("No pude abrir Google Traductor.")
    return f"Google Traductor abierto para traducir: {source}" if source else "Google Traductor abierto."


def open_google(service: str) -> str:
    url = GOOGLE_URLS.get(service)
    if not url:
        raise ActionUnavailable("Servicio Google desconocido.")
    if not webbrowser.open_new_tab(url):
        raise ActionUnavailable("No pude solicitar al navegador que abra Google.")
    return f"Abriendo {service.replace('_', ' ')}. Comprueba el inicio de sesión."


def shutdown_windows() -> str:
    """Request an immediate, normal Windows shutdown.

    Do not use /f (forced closing), elevated commands, shell=True, or a
    nonzero /t that implicitly forces applications to close. Windows may
    still pause shutdown for unsaved documents, by design.
    """
    if sys.platform!="win32":
        raise ActionUnavailable("Apagar el equipo requiere Windows.")
    try:
        subprocess.Popen(["shutdown.exe","/s","/t","0"],shell=False)
    except OSError as exc:
        raise ActionUnavailable(
            "Windows no aceptó la solicitud de apagado."
        ) from exc
    return ("Solicité apagar Windows. Si hay cambios sin guardar, "
            "Windows puede esperar para protegerlos.")


def open_windows_app(app: str) -> str:
    if sys.platform != "win32":
        raise ActionUnavailable("Esta acción requiere Windows.")
    allowed = {
        "calculator": ["calc.exe"],
        "notepad": ["notepad.exe"],
        "paint": ["mspaint.exe"],
        "explorer": ["explorer.exe"],
        "task_manager": ["taskmgr.exe"],
        "terminal": ["cmd.exe"],
        "downloads": ["explorer.exe","shell:Downloads"],
        "documents": ["explorer.exe","shell:Personal"],
    }
    if app=="vscode":
        import shutil
        options=[
            shutil.which("Code.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA",""),"Programs",
                         "Microsoft VS Code","Code.exe"),
            os.path.join(os.environ.get("ProgramFiles",""),"Microsoft VS Code",
                         "Code.exe"),
        ]
        executable=next(
            (p for p in options if p and os.path.isfile(p)),None)
        if not executable:
            raise ActionUnavailable(
                "No encontré Visual Studio Code instalado para este usuario.")
        # VS Code's Electron/Node stdout and stderr must not inherit HOVER's
        # microphone console. Otherwise startup warnings swamp ASR logs.
        subprocess.Popen([executable],shell=False,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return "Solicité abrir Visual Studio Code."
    if app == "settings":
        os.startfile("ms-settings:")
        return "Configuración de Windows solicitada."
    command = allowed.get(app)
    if command is None:
        raise ActionUnavailable("Aplicación no permitida.")
    subprocess.Popen(command, shell=False)
    labels = {"calculator":"Calculadora abierta.","notepad":"Bloc de notas abierto.",
              "paint":"Paint abierto.","explorer":"Explorador abierto.",
              "task_manager":"Abriendo el Administrador de tareas.",
              "terminal":"Abriendo la terminal de Windows.",
              "downloads":"Abriendo Descargas.","documents":"Abriendo Documentos."}
    return labels[app]


def new_office_document(kind: str) -> str:
    if sys.platform != "win32":
        raise ActionUnavailable("Microsoft Office local requiere Windows.")
    apps = {
        "word": ("Word.Application", "Documents", "Word"),
        "excel": ("Excel.Application", "Workbooks", "Excel"),
        "powerpoint": ("PowerPoint.Application", "Presentations", "PowerPoint"),
    }
    if kind not in apps:
        raise ActionUnavailable("Aplicación de Office no admitida.")
    try:
        import win32com.client
    except ImportError as exc:
        raise ActionUnavailable(
            "Instala el soporte opcional de Microsoft Office con: "
            r".\.venv\Scripts\python.exe -m pip install pywin32"
        ) from exc
    progid, collection, title = apps[kind]
    try:
        app = win32com.client.Dispatch(progid)
        app.Visible = True
        getattr(app, collection).Add()
    except Exception as exc:
        raise ActionUnavailable(
            f"No pude crear el documento en {title}. Comprueba que esté instalado y activado."
        ) from exc
    return f"Nuevo documento de {title} abierto; todavía no está guardado."


def new_word_document() -> str:
    return new_office_document("word")

def _selected_explorer_path() -> Path | None:
    """Only use the selected item of the foreground Windows Explorer window."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import win32com.client
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        shell = win32com.client.Dispatch("Shell.Application")
        for window in shell.Windows():
            if int(window.HWND) != int(hwnd):
                continue
            selection = window.Document.SelectedItems()
            if selection.Count != 1:
                return None
            return Path(selection.Item(0).Path)
    except Exception:
        return None
    return None


def _document_roots() -> list[Path]:
    home = Path.home()
    roots = [home/"Documents", home/"Downloads", home/"Desktop",
             home/"OneDrive"/"Documents", home/"OneDrive"/"Desktop"]
    return [p for p in roots if p.is_dir()]


def _find_named_document(name: str) -> Path:
    wanted = name.casefold().strip()
    if len(wanted) < 2:
        raise ActionUnavailable("Dime un nombre más específico del documento.")
    matches: list[Path] = []
    for root in _document_roots():
        # Only two folder levels: avoid searching huge directory trees.
        for pattern in ("*", "*/*", "*/*/*"):
            for path in root.glob(pattern):
                if path.is_file() and path.suffix.lower() in DOCUMENT_TYPES:
                    if wanted in path.stem.casefold():
                        matches.append(path)
                        if len(matches) >= 12:
                            break
            if len(matches) >= 12:
                break
    distinct = list(dict.fromkeys(p.resolve() for p in matches))
    if not distinct:
        raise ActionUnavailable(f"No encontré un documento llamado {name!r} en Documentos o Descargas.")
    if len(distinct) > 1:
        preview = ", ".join(p.name for p in distinct[:4])
        raise ActionUnavailable(f"Encontré varios documentos: {preview}. Dime un nombre más preciso.")
    return distinct[0]


def open_document(name: str = "") -> str:
    if sys.platform != "win32":
        raise ActionUnavailable("Abrir documentos locales requiere Windows.")
    target = _find_named_document(name) if name else _selected_explorer_path()
    if target is None:
        raise ActionUnavailable(
            "Selecciona un único documento en el Explorador o dime su nombre. "
            "Por ejemplo: Hover, abre el documento Taller 3."
        )
    if not target.is_file() or target.suffix.lower() not in DOCUMENT_TYPES:
        raise ActionUnavailable("Solo abro documentos de formatos permitidos, no programas ni scripts.")
    os.startfile(str(target))
    return f"Documento abierto: {target.name}"


def _spotify_session_play() -> str:
    """Request PLAY only from a Spotify Windows media session.

    No generic global play/pause: it could pause another application. Never
    report success unless Windows confirms playback state as PLAYING.
    """
    try:
        import asyncio
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Manager)
        except ImportError:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Manager)

        async def resume():
            manager=await Manager.request_async()
            sessions=list(manager.get_sessions())
            spotify=[session for session in sessions
                     if "spotify" in str(session.source_app_user_model_id).lower()]
            if not spotify:
                return "no_session"
            for session in spotify:
                try:
                    before=session.get_playback_info()
                    if "playing" in str(before.playback_status).lower():
                        return "playing"
                    accepted=await session.try_play_async()
                    if accepted:
                        after=session.get_playback_info()
                        if "playing" in str(after.playback_status).lower():
                            return "playing"
                        return "requested"
                except Exception:
                    continue
            return "failed"
        return asyncio.run(resume())
    except ImportError:
        return "missing_api"
    except Exception:
        return "failed"


def spotify_start_playback(open_app: bool = True, *, play: bool = True) -> str:
    """Launch Spotify, optionally resume an EXISTING user-selected track.

    Opening an app is not the same as starting audio. No Spotify Web API
    credentials are stored here and HOVER never claims unverified playback.
    """
    if sys.platform!="win32":
        raise ActionUnavailable("Spotify por voz necesita Windows.")
    if open_app:
        try:
            os.startfile("spotify:")
            opened=True
        except (OSError,AttributeError):
            opened=bool(webbrowser.open_new_tab("https://open.spotify.com/"))
        if not opened:
            raise ActionUnavailable("No se pudo abrir Spotify. Revisa su instalación.")
    if not play:
        return ("Spotify abierto. Para reproducir, selecciona una canción o "
                "lista y di 'Hover, reproduce Spotify'.")
    # Allow a newly opened desktop client to register its session. The first
    # call can still be sessionless until a song is selected by the user.
    import time
    state="no_session"
    for attempt in range(3 if open_app else 1):
        if open_app:
            time.sleep(0.8)
        state=_spotify_session_play()
        if state in ("playing","requested","missing_api","failed"):
            break
    if state=="playing":
        return "Spotify confirma una sesión de reproducción activa en Windows."
    if state=="requested":
        return ("Spotify aceptó la solicitud de reproducir, pero Windows "
                "todavía no confirmó el audio.")
    if state=="missing_api":
        return ("Spotify abierto; falta el controlador multimedia de Windows. "
                "Instala requirements.txt para permitir reanudar canciones.")
    if state=="no_session":
        return ("Spotify abierto, pero Windows no detectó una sesión con una canción. "
                "Selecciona una canción o lista en Spotify una vez y luego "
                "di 'Hover, reproduce Spotify'.")
    return ("Spotify no confirmó reproducción. Comprueba que la aplicación "
            "esté abierta y haya una canción seleccionada.")


def send_media_key(key: str) -> str:
    """Send a Windows global media key. Does not select a particular player."""
    if sys.platform != "win32":
        raise ActionUnavailable("Controles multimedia disponibles en Windows.")
    keys = {
        "play_pause":0xB3, "next":0xB0, "previous":0xB1,
        "volume_mute":0xAD, "volume_down":0xAE, "volume_up":0xAF,
    }
    vk = keys.get(key)
    if vk is None:
        raise ActionUnavailable("Comando multimedia no permitido.")
    import ctypes
    user32 = ctypes.windll.user32
    for _ in range(3 if key in ("volume_down", "volume_up") else 1):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
    messages = {
        "play_pause":"Envié reproducir/pausar al reproductor multimedia activo.",
        "next":"Envié siguiente pista al reproductor activo.",
        "previous":"Envié pista anterior al reproductor activo.",
        "volume_mute":"Alterné silencio de Windows.",
        "volume_up":"Solicité subir el volumen de Windows.",
        "volume_down":"Solicité bajar el volumen de Windows.",
    }
    return messages[key]


def _foreground_is_google_browser() -> bool:
    """Check title and executable; never send Ctrl+W to an arbitrary app."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    # Explicit Win64 signatures: default ctypes pointer values could be truncated.
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    titlebuf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, titlebuf, 512)
    title = titlebuf.value.casefold().strip()
    # Do not treat every Chrome window as Google (its title always has 'Chrome').
    if "google" not in title and "gmail" not in title:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    # PROCESS_QUERY_LIMITED_INFORMATION
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, pid.value)
    if not process:
        return False
    try:
        filename = ctypes.create_unicode_buffer(1024)
        length = wintypes.DWORD(len(filename))
        ok = kernel32.QueryFullProcessImageNameW(process, 0, filename, ctypes.byref(length))
        if not ok:
            return False
        executable = Path(filename.value).name.casefold()
        return executable in {"chrome.exe","msedge.exe","firefox.exe","brave.exe","opera.exe"}
    finally:
        kernel32.CloseHandle(process)


def close_google_tab() -> str:
    if sys.platform != "win32":
        raise ActionUnavailable("Cerrar una pestaña requiere Windows.")
    if not _foreground_is_google_browser():
        raise ActionUnavailable(
            "No cerraré otra aplicación: primero deja al frente la pestaña de Google."
        )
    import ctypes
    user32 = ctypes.windll.user32
    VK_CONTROL, VK_W = 0x11, 0x57
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_W, 0, 0, 0)
    user32.keybd_event(VK_W, 0, 2, 0)
    user32.keybd_event(VK_CONTROL, 0, 2, 0)
    return "Se envió cerrar pestaña de Google al navegador activo."

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

class ActionUnavailable(RuntimeError):
    pass


def open_google(service: str) -> str:
    url = GOOGLE_URLS.get(service)
    if not url:
        raise ActionUnavailable("Servicio Google desconocido.")
    if not webbrowser.open_new_tab(url):
        raise ActionUnavailable("No pude solicitar al navegador que abra Google.")
    return f"Abriendo {service.replace('_', ' ')}. Comprueba el inicio de sesión."


def open_windows_app(app: str) -> str:
    if sys.platform != "win32":
        raise ActionUnavailable("Esta acción requiere Windows.")
    allowed = {
        "calculator": "calc.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
    }
    executable = allowed.get(app)
    if executable is None:
        raise ActionUnavailable("Aplicación no permitida.")
    subprocess.Popen([executable], shell=False)
    return {"calculator":"Calculadora abierta.", "notepad":"Bloc de notas abierto.",
            "paint":"Paint abierto.", "explorer":"Explorador abierto."}[app]


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

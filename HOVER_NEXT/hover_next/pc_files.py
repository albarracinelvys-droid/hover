"""Deterministic, scoped file operations for HOVER on Windows.

No shell execution, recursion, arbitrary paths, overwrites, or permanent deletion.
Only the current user's Desktop, Downloads, Documents and selected favorite folder.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import threading
import time

from .local_files import safe_basename, selected_folder


class PCFileError(RuntimeError):
    pass


KINDS = {
    "archive": (".zip", ".rar", ".7z", ".tar", ".tar.gz", ".tgz", ".gz", ".bz2"),
    "pdf": (".pdf",),
    "excel": (".xlsx", ".xls", ".xlsm", ".csv"),
    "image": (".jpg", ".jpeg", ".png", ".webp", ".gif"),
    "text": (".txt", ".md"),
    "any": (),
}
MAX_TEXT_BYTES = 1024 * 1024
# Track only a move completed in THIS HOVER process. Never infer a prior
# move from a folder's modification times (OneDrive may reorder them).
# The short history avoids deleting an unrelated old file after a restart.
LAST_MOVE_MAX_AGE = 1800
_LAST_MOVED = None
_LAST_MOVE_LOCK = threading.Lock()


def _remember_move(target: Path, location_key: str) -> None:
    global _LAST_MOVED
    stat=target.stat()
    record={
        "location":location_key,
        "name":target.name,
        "size":str(stat.st_size),
        "mtime_ns":str(stat.st_mtime_ns),
        "when":time.monotonic(),
    }
    with _LAST_MOVE_LOCK:
        _LAST_MOVED=record


def _recent_move(location_key: str) -> dict:
    with _LAST_MOVE_LOCK:
        record=dict(_LAST_MOVED) if _LAST_MOVED is not None else None
    if (record is None or record["location"]!=location_key
            or not (0 <= time.monotonic()-record["when"] <= LAST_MOVE_MAX_AGE)):
        raise PCFileError(
            "No hay un archivo movido recientemente por HOVER a esa carpeta "
            "en esta sesión. No eliminé nada.")
    return record


def _forget_last_move(folder_key: str, name: str) -> None:
    global _LAST_MOVED
    with _LAST_MOVE_LOCK:
        if (_LAST_MOVED and _LAST_MOVED["location"]==folder_key
                and _LAST_MOVED["name"]==name):
            _LAST_MOVED=None


def _known_folder(name: str) -> Path:
    home = Path.home()
    names = {"desktop": "Desktop", "downloads": "Downloads",
             "documents": "Documents"}
    if name not in names:
        raise PCFileError("Ubicación no permitida.")
    # Windows often redirects Desktop/Documents to OneDrive. Read the
    # current user's shell folders rather than guessing ~/Desktop.
    try:
        import winreg
        reg_names = {
            "desktop": "Desktop",
            "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
            "documents": "Personal",
        }
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        ) as key:
            value, _ = winreg.QueryValueEx(key, reg_names[name])
        path = Path(os.path.expandvars(str(value))).expanduser()
        if path.is_dir():
            return path.resolve(strict=True)
    except (ImportError, OSError, ValueError):
        pass
    fallback = home / names[name]
    if fallback.is_dir():
        return fallback.resolve(strict=True)
    raise PCFileError(
        f"No encuentro la carpeta {names[name]} del usuario. "
        "Configúrala en Windows antes de mover archivos."
    )


def location(name: str, config: dict) -> Path:
    if name == "favorite":
        return selected_folder(config)
    return _known_folder(name)


def _direct_child(folder: Path, basename: str, *, files_only=False) -> Path:
    basename=safe_basename(basename)
    path=folder / basename
    if not path.exists() or path.is_symlink() or (files_only and not path.is_file()):
        raise PCFileError(f"No encuentro {basename} directamente en {folder}.")
    if not path.is_file() and not path.is_dir():
        raise PCFileError("No se permite modificar este tipo de elemento.")
    return path


def _latest(folder: Path, kind: str) -> Path:
    if kind not in KINDS:
        raise PCFileError("Tipo de archivo no permitido.")
    suffixes=KINDS[kind]
    candidates=[]
    for item in folder.iterdir():
        if not item.is_file() or item.is_symlink():
            continue
        name=item.name.lower()
        if name.startswith(".") or name.endswith((".part", ".crdownload", ".tmp")):
            continue
        if suffixes and not any(name.endswith(ext) for ext in suffixes):
            continue
        candidates.append(item)
    if not candidates:
        raise PCFileError(f"No hay archivos de tipo {kind} en {folder}.")
    return max(candidates,key=lambda p:(p.stat().st_mtime,p.name))


def _unique_destination(folder: Path, name: str) -> Path:
    name=safe_basename(name)
    target=folder / name
    stem, suffix=Path(name).stem, Path(name).suffix
    counter=2
    while target.exists() or target.is_symlink():
        target=folder / f"{stem} ({counter}){suffix}"
        counter+=1
        if counter>1000:
            raise PCFileError("Hay demasiados archivos con nombres similares.")
    return target


def prepare_transfer(args: dict, config: dict) -> dict:
    """Freeze the exact latest filename before a visual confirmation dialog."""
    if args.get("pick") != "latest":
        return dict(args)
    folder=location(args["from"],config)
    source=_latest(folder,args.get("kind","any"))
    result=dict(args)
    result.update({"pick":"name","name":source.name,
                   "size":str(source.stat().st_size),
                   "mtime_ns":str(source.stat().st_mtime_ns)})
    return result


def prepare_delete(args: dict, config: dict) -> dict:
    """Freeze the target before directly moving it to the Recycle Bin.

    Only files directly inside an explicitly named user folder are accepted.
    Directory trees and symlinks are never deleted by a voice command.
    """
    folder=location(args["location"],config)
    if args.get("pick")=="last_moved":
        # Only a completed HOVER move, not whatever file is most recent.
        record=_recent_move(args["location"])
        source=_direct_child(folder,record["name"],files_only=True)
        stat=source.stat()
        if (str(stat.st_size)!=record["size"] or
                str(stat.st_mtime_ns)!=record["mtime_ns"]):
            raise PCFileError("El archivo movido por HOVER cambió. No eliminé nada.")
    elif args.get("pick")=="latest":
        source=_latest(folder,args.get("kind","any"))
    elif args.get("pick")=="name":
        source=_direct_child(folder,args["name"],files_only=True)
    else:
        raise PCFileError("Debes identificar un archivo concreto.")
    stat=source.stat()
    return {"pick":"name","location":args["location"],
            "name":source.name,"size":str(stat.st_size),
            "mtime_ns":str(stat.st_mtime_ns)}


def _new_file_target(folder: Path, name: str, extension: str) -> Path:
    """Require the correct document suffix and exclusive file creation."""
    name=safe_basename(name)
    suffix=Path(name).suffix.casefold()
    if suffix and suffix!=extension:
        raise PCFileError(
            f"El nombre termina en {suffix}, pero este tipo necesita {extension}. "
            "No crearé otro formato por error.")
    if not suffix:
        name+=extension
    target=folder / name
    if target.exists() or target.is_symlink():
        raise PCFileError(f"Ya existe {target.name}; no sobrescribí el archivo.")
    return target


def create_saved_file(folder: Path, kind: str, name: str) -> str:
    """Write a valid, empty user document to disk using exclusive creation."""
    extensions={"text":".txt","excel":".xlsx","word":".docx","csv":".csv"}
    if kind not in extensions:
        raise PCFileError("Tipo de documento no compatible.")
    target=_new_file_target(folder,name,extensions[kind])
    if kind in ("text","csv"):
        with target.open("x",encoding="utf-8-sig" if kind=="csv" else "utf-8"):
            pass
    elif kind=="excel":
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise PCFileError("Falta openpyxl. Instala requirements.txt.") from exc
        wb=Workbook()
        wb.active.title="Hoja1"
        try:
            with target.open("xb") as handle:
                try:
                    wb.save(handle)
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
        finally:
            wb.close()
    elif kind=="word":
        try:
            from docx import Document
        except ImportError as exc:
            raise PCFileError("Falta python-docx. Instala requirements.txt.") from exc
        with target.open("xb") as handle:
            try:
                Document().save(handle)
            except Exception:
                target.unlink(missing_ok=True)
                raise
    if not target.is_file() or target.stat().st_size==0 and kind in ("excel","word"):
        raise PCFileError("El archivo no se pudo guardar correctamente.")
    return f"Creé y guardé el archivo {target}."


def close_foreground_window(app: str) -> str:
    """Ask ONE active user window to close normally (WM_CLOSE), never kill it."""
    try:
        import win32gui
        import win32con
    except ImportError as exc:
        raise PCFileError("Para controlar ventanas en Windows se necesita pywin32.") from exc
    hwnd=win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindowVisible(hwnd):
        raise PCFileError("No hay una ventana activa que pueda cerrar.")
    title=win32gui.GetWindowText(hwnd).strip()
    clazz=win32gui.GetClassName(hwnd)
    # Never close the shell, invisible windows, elevated system dialogs or
    # HOVER itself by an uncertain Whisper transcription.
    blocked={"Progman","WorkerW","Shell_TrayWnd","DV2ControlHost"}
    if (not title or clazz in blocked or "HOVER" in title.upper()
            or title.casefold() in ("program manager","administrador de tareas")):
        raise PCFileError("Esa ventana está protegida. No la cerré.")
    expected={
        "excel":("XLMAIN","excel"),
        "word":("OpusApp","word"),
        "powerpoint":("PPTFrameClass","powerpoint"),
        "calculator":("ApplicationFrameWindow","calculadora"),
        "notepad":("Notepad","bloc de notas"),
        "paint":("MSPaintApp","paint"),
        "explorer":("CabinetWClass","explorador de archivos"),
    }
    if app!="foreground":
        if app not in expected:
            raise PCFileError("Solo cierro aplicaciones conocidas al frente.")
        window_class, label=expected[app]
        if clazz!=window_class and label not in title.casefold():
            raise PCFileError(
                f"La ventana activa no corresponde a {app}. No cerré otra aplicación.")
    # Windows WM_CLOSE is graceful: unsaved changes remain protected by the
    # application's own confirmation; no TerminateProcess or taskkill is used.
    win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
    return f"Solicité cerrar la ventana activa: {title}. La aplicación puede pedir guardar cambios."


def perform(action: str, args: dict, config: dict) -> str:
    if action == "pc_delete":
        # Only a fresh, frozen file snapshot is eligible for deletion.
        if (args.get("pick")!="name" or
                "size" not in args or "mtime_ns" not in args):
            raise PCFileError("Falta la selección verificada del archivo.")
        folder=location(args["location"],config)
        source=_direct_child(folder,args["name"],files_only=True)
        now=source.stat()
        if (str(now.st_size)!=args["size"] or
                str(now.st_mtime_ns)!=args["mtime_ns"]):
            raise PCFileError("El archivo cambió desde la orden. No lo eliminé.")
        try:
            from send2trash import send2trash
        except ImportError as exc:
            raise PCFileError(
                "Falta Send2Trash. Instálalo con pip install -r requirements.txt."
            ) from exc
        try:
            send2trash(str(source))
        except OSError as exc:
            raise PCFileError("Windows no pudo enviar el archivo a la Papelera.") from exc
        _forget_last_move(args["location"],source.name)
        return f"Envié {source.name} a la Papelera de reciclaje de Windows."

    if action == "pc_transfer":
        source_folder=location(args["from"],config)
        destination_folder=location(args["to"],config)
        if source_folder == destination_folder:
            raise PCFileError("El origen y el destino son la misma carpeta.")
        if args.get("pick") == "latest":
            source=_latest(source_folder,args.get("kind","any"))
        else:
            source=_direct_child(source_folder,args["name"],files_only=True)
        # Do not silently switch to another "latest" download after the
        # user approves the filename in the Windows confirmation dialog.
        if "size" in args and (
            str(source.stat().st_size)!=args["size"] or
            str(source.stat().st_mtime_ns)!=args["mtime_ns"]
        ):
            raise PCFileError("El archivo cambió tras la confirmación. Repite la orden.")
        destination=_unique_destination(destination_folder,source.name)
        if args["operation"] == "move":
            shutil.move(str(source),str(destination))
            try:
                _remember_move(destination,args["to"])
            except OSError:
                # Moving succeeded; a journal failure must not claim failure
                # or allow an unsafe "last moved" deletion afterwards.
                with _LAST_MOVE_LOCK:
                    global _LAST_MOVED
                    _LAST_MOVED=None
            return f"Moví {source.name} de {source_folder} a {destination}."
        if args["operation"] == "copy":
            shutil.copy2(source,destination)
            return f"Copié {source.name} de {source_folder} a {destination}."
        raise PCFileError("Operación no admitida.")

    if action == "pc_rename":
        folder=location(args["location"],config)
        source=_direct_child(folder,args["old"])
        new=safe_basename(args["new"])
        target=folder / new
        if target.exists() or target.is_symlink():
            raise PCFileError(f"Ya existe {new}; no sobrescribí ningún elemento.")
        source.rename(target)
        return f"Renombré {source.name} como {target.name} en {folder}."

    if action == "pc_create":
        folder=location(args["location"],config)
        name=safe_basename(args["name"])
        if args["kind"]=="folder":
            target=folder / name
            target.mkdir(exist_ok=False)
            return f"Creé la carpeta {target}."
        return create_saved_file(folder,args["kind"],name)

    if action == "pc_close_window":
        return close_foreground_window(args["app"])

    if action == "pc_append":
        folder=location(args["location"],config)
        name=safe_basename(args["name"])
        if not name.lower().endswith((".txt",".md")):
            raise PCFileError("La edición por voz se limita a TXT y Markdown.")
        target=_direct_child(folder,name,files_only=True)
        if target.stat().st_size > MAX_TEXT_BYTES:
            raise PCFileError("El archivo es demasiado grande para editarlo por voz.")
        text=str(args["text"]).strip()
        if not text or len(text)>500:
            raise PCFileError("El texto dictado debe tener entre 1 y 500 caracteres.")
        with target.open("a",encoding="utf-8") as handle:
            handle.write(text+"\n")
        return f"Agregué texto al final de {target}. No se borró su contenido."

    raise PCFileError("Acción de archivos no admitida.")

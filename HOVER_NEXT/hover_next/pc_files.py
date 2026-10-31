"""Deterministic, scoped file operations for HOVER on Windows.

No shell execution, recursion, arbitrary paths, overwrites, or permanent deletion.
Only the current user's Desktop, Downloads, Documents and selected favorite folder.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil

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
    """Freeze the target before asking for a separate spoken confirmation.

    Only files directly inside an explicitly named user folder are accepted.
    Directory trees and symlinks are never deleted by a voice command.
    """
    folder=location(args["location"],config)
    if args.get("pick")=="latest":
        source=_latest(folder,args.get("kind","any"))
    elif args.get("pick")=="name":
        source=_direct_child(folder,args["name"],files_only=True)
    else:
        raise PCFileError("Debes identificar un archivo concreto.")
    stat=source.stat()
    return {"pick":"name","location":args["location"],
            "name":source.name,"size":str(stat.st_size),
            "mtime_ns":str(stat.st_mtime_ns)}


def perform(action: str, args: dict, config: dict) -> str:
    if action == "pc_delete":
        # Only run after VoiceDialogue receives an unambiguous spoken "sí"
        # for a specific snapshot and the executor marks it confirmed.
        if (args.get("pick")!="name" or
                "size" not in args or "mtime_ns" not in args):
            raise PCFileError("Falta la selección verificada del archivo.")
        folder=location(args["location"],config)
        source=_direct_child(folder,args["name"],files_only=True)
        now=source.stat()
        if (str(now.st_size)!=args["size"] or
                str(now.st_mtime_ns)!=args["mtime_ns"]):
            raise PCFileError("El archivo cambió desde la confirmación. No lo eliminé.")
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
        if args["kind"]=="text":
            target=folder / (name if name.lower().endswith(".txt") else name+".txt")
            with target.open("x",encoding="utf-8"):
                pass
            return f"Creé el archivo de texto {target}."
        raise PCFileError("Solo se permite crear carpetas o archivos TXT.")

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

"""Safe creation of files and folders inside HOVER's existing favorite folder.

Windhawk stores the selected folder in UTF-16 at:
  %APPDATA%/HOVER/carpeta_favorita.txt
No silent fallback to Desktop, Downloads or an arbitrary working directory.
"""
from __future__ import annotations
import os
import re
from pathlib import Path


class FavoriteFolderError(RuntimeError):
    pass


def selected_folder(config: dict) -> Path:
    # The shared Windhawk favorite is the user's visible choice in the UI.
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    reference = appdata / "HOVER" / "carpeta_favorita.txt"
    folder = None
    if reference.is_file():
        try:
            raw = reference.read_bytes()
            if len(raw) > 2048 or not raw.startswith(b"\xff\xfe"):
                raise ValueError("Ruta favorita con formato inválido")
            path = raw.decode("utf-16").strip("\x00\r\n ")
            if path:
                folder = Path(path).expanduser()
        except (OSError, UnicodeError, ValueError) as exc:
            raise FavoriteFolderError(
                "La carpeta de Atajos no se pudo leer. Selecciónala de nuevo."
            ) from exc
    elif config.get("folder"):
        folder = Path(config["folder"]).expanduser()
    if folder is None:
        raise FavoriteFolderError(
            "Primero elige una carpeta con clic derecho en Carpeta, dentro de Atajos."
        )
    if not folder.is_dir():
        raise FavoriteFolderError(f"La carpeta configurada ya no existe: {folder}")
    return folder.resolve(strict=True)


def safe_basename(value: str) -> str:
    name = value.strip().rstrip(" .")
    if not 1 <= len(name) <= 100:
        raise ValueError("El nombre debe tener entre 1 y 100 caracteres.")
    if name in (".", "..") or any(c in name for c in '\\\\/<>:"|?*'):
        raise ValueError("El nombre no puede incluir rutas ni caracteres especiales.")
    if re.search(r"[\x00-\x1f]", name):
        raise ValueError("Caracteres de control no permitidos.")
    stem = name.split(".")[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)},
                *{f"LPT{i}" for i in range(1, 10)}}:
        raise ValueError("Nombre reservado de Windows.")
    return name


def create_item(config: dict, kind: str, name: str) -> str:
    folder = selected_folder(config)
    basename = safe_basename(name)
    if kind == "txt":
        filename = basename if basename.casefold().endswith(".txt") else basename + ".txt"
        target = folder / filename
        try:
            with target.open("x", encoding="utf-8") as handle:
                handle.write("")
        except FileExistsError as exc:
            raise FavoriteFolderError(
                f"Ya existe {target.name}; no sobrescribí ningún archivo."
            ) from exc
        return f"Archivo TXT creado en tu carpeta de HOVER: {target}"
    if kind == "folder":
        target = folder / basename
        try:
            target.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise FavoriteFolderError(
                f"Ya existe la carpeta {target.name}; no hice cambios."
            ) from exc
        return f"Subcarpeta creada: {target}"
    if kind == "excel":
        import sys
        if sys.platform != "win32":
            raise FavoriteFolderError("Crear Excel en Office requiere Windows.")
        filename = basename if basename.casefold().endswith(".xlsx") else basename + ".xlsx"
        target = folder / filename
        if target.exists():
            raise FavoriteFolderError(
                f"Ya existe {filename}; no sobrescribí el libro."
            )
        try:
            import win32com.client
        except ImportError as exc:
            raise FavoriteFolderError("Falta pywin32 para Microsoft Excel.") from exc
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            wb = excel.Workbooks.Add()
            wb.SaveAs(str(target), FileFormat=51)
        except Exception as exc:
            raise FavoriteFolderError(
                "Excel no pudo guardar el libro. Comprueba Office y la carpeta."
            ) from exc
        return f"Libro de Excel creado y guardado: {target}"
    raise FavoriteFolderError("Tipo de archivo no permitido.")

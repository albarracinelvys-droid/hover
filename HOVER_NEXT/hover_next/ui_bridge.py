"""Silent Windhawk status bridge; shows states in HOVER without text-to-speech.

Format matches HOVER_v4_1: serial<TAB>state<TAB>page<TAB>message.
Only local temporary files are written; no network connection.
"""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import time

ALLOWED = {"idle", "listening", "thinking", "ok", "error"}

def bridge_file() -> Path:
    path = Path(tempfile.gettempdir()) / "WindhawkIslandPremium"
    path.mkdir(parents=True, exist_ok=True)
    return path / "voice_ui.txt"

def publish(state: str, message: str = "", page: int = -1) -> bool:
    if state not in ALLOWED:
        raise ValueError("Estado de interfaz no permitido")
    safe = str(message).replace("\t", " ").replace("\r", " ").replace("\n", " ")[:115]
    payload = f"{time.time_ns()}\t{state}\t{int(page)}\t{safe}"
    target = bridge_file()
    tmp = target.with_suffix(f".{os.getpid()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)
        return True
    except OSError as exc:
        print(f"[ui] No pude actualizar la isla: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False

def status_page(action: str) -> int:
    """Built-in HOVER tabs: Musica, Copias, Calendario, Atajos, Equipo."""
    if action == "spotify_play":
        return 0
    if action in ("copy_latest_download","move_latest_download"):
        return 1
    if action in ("open_site", "new_chat", "new_chat_and_send", "open_project",
                  "close_tab", "send_prompt", "upload_file", "create_private_repo"):
        return 3
    if action in ("show_pc",):
        return 4
    return -1

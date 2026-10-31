"""Silent Windhawk status bridge; shows states in HOVER without text-to-speech.

Format matches HOVER_v4_1: serial<TAB>state<TAB>page<TAB>message.
Only local temporary files are written; no network connection.
"""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import time
import threading
import uuid

ALLOWED = {"idle", "listening", "thinking", "ok", "error"}

def bridge_file() -> Path:
    path = Path(tempfile.gettempdir()) / "WindhawkIslandPremium"
    path.mkdir(parents=True, exist_ok=True)
    return path / "voice_ui.txt"

# Lock within the process; UUIDs avoid collisions between multiple HOVER
# instances. Windhawk can briefly hold the destination open without Windows
# FILE_SHARE_DELETE, so os.replace may need a bounded retry.
_WRITE_LOCK = threading.Lock()
_LAST_WARNING = 0.0

def publish(state: str, message: str = "", page: int = -1) -> bool:
    global _LAST_WARNING
    if state not in ALLOWED:
        raise ValueError("Estado de interfaz no permitido")
    safe = str(message).replace("\t", " ").replace("\r", " ").replace("\n", " ")[:115]
    payload = f"{time.time_ns()}\t{state}\t{int(page)}\t{safe}"
    with _WRITE_LOCK:
        target=bridge_file()
        tmp=target.with_name(f"voice_ui.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        last_error=None
        try:
            tmp.write_text(payload,encoding="utf-8")
            for attempt in range(7):
                try:
                    os.replace(tmp,target)
                    return True
                except (PermissionError,OSError) as exc:
                    # Only transient file-sharing/permission errors get
                    # a short retry. Other unexpected problems return False.
                    last_error=exc
                    winerror=getattr(exc,"winerror",None)
                    if winerror not in (5,32,33) and not isinstance(exc,PermissionError):
                        break
                    if attempt!=6:
                        time.sleep(min(0.04*(attempt+1),0.20))
        except OSError as exc:
            last_error=exc
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        # Throttle warnings: one locked file must not flood microphone logs.
        now=time.monotonic()
        if now-_LAST_WARNING>20.0:
            _LAST_WARNING=now
            print("[ui] Estado de Windhawk ocupado; lo reintentaré. "
                  "Si persiste, cierra instancias duplicadas de HOVER. "
                  f"Detalle: {type(last_error).__name__}",flush=True)
        return False

def status_page(action: str) -> int:
    """Built-in HOVER tabs: Musica, Copias, Calendario, Atajos, Equipo."""
    if action == "spotify_play":
        return 0
    if action in ("copy_latest_download","move_latest_download"):
        return 1
    if action in ("chat_prepare", "chat_compose", "chat_send_prepared",
                  "google_app", "windows_app", "office_new", "open_document"):
        return 3
    if action in ("open_site", "new_chat", "new_chat_and_send", "open_project",
                  "close_tab", "send_prompt", "upload_file", "create_private_repo"):
        return 3
    if action in ("show_pc",):
        return 4
    return -1

"""Start HOVER v5 as a truly detached Windows GUI-subsystem process.

The batch/PowerShell process returns immediately. Whisper, Calendar, Spotify
and their existing worker threads keep running in pythonw.exe. Diagnostics are
written to a per-user local log rather than discarded. A PID record is only
trusted after verifying the live process command line with psutil.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


class BackgroundLaunchError(RuntimeError):
    pass


def state_paths():
    root=Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())/"HOVER_NEXT"
    root.mkdir(parents=True,exist_ok=True)
    return root/"voice.pid",root/"voice.log"


def is_hover_voice_process(pid):
    """Avoid killing a different Python process after Windows reuses a PID."""
    if not isinstance(pid,int) or pid<=0:
        return False
    try:
        import psutil
        process=psutil.Process(pid)
        if not process.is_running() or process.status()==psutil.STATUS_ZOMBIE:
            return False
        cmdline=[str(x).casefold() for x in process.cmdline()]
        return ("-m" in cmdline and "hover_next.app" in cmdline
                and "--voice" in cmdline)
    except (ImportError,ValueError,OSError):
        return False
    except Exception:
        return False


def current_pid():
    path,_=state_paths()
    try:
        pid=int(path.read_text(encoding="ascii").strip())
    except (OSError,ValueError):
        return None
    return pid if is_hover_voice_process(pid) else None


def _running_hover_process():
    """Detect even an older console-launched instance of the same voice app."""
    recorded=current_pid()
    if recorded is not None:
        return recorded
    try:
        import psutil
        for process in psutil.process_iter(attrs=["pid","cmdline"]):
            cmd=[str(x).casefold() for x in (process.info.get("cmdline") or [])]
            if "-m" in cmd and "hover_next.app" in cmd and "--voice" in cmd:
                return int(process.info["pid"])
    except (ImportError,ValueError,OSError):
        pass
    return None


def start(*,engine="auto",mic=None,threshold=None):
    if sys.platform!="win32":
        raise BackgroundLaunchError("El inicio sin terminal requiere Windows.")
    previous=_running_hover_process()
    if previous is not None:
        print(f"HOVER ya está activo sin consola (PID {previous}).",flush=True)
        return 0
    exe=Path(sys.executable).with_name("pythonw.exe")
    if not exe.is_file():
        raise BackgroundLaunchError(
            "No encontré pythonw.exe en .venv. Reinstala el entorno virtual.")
    pid_path,log_path=state_paths()
    workdir=Path(__file__).resolve().parents[1]
    creationflags=getattr(subprocess,"DETACHED_PROCESS",0x00000008)
    command=[str(exe),"-m","hover_next.app","--voice","--model","small",
             "--engine",engine]
    if mic is not None:
        command.extend(["--mic",str(mic)])
    if threshold is not None:
        command.extend(["--threshold",str(threshold)])
    with log_path.open("a",encoding="utf-8") as log:
        log.write("\n[launcher] Iniciando HOVER v5 sin terminal.\n")
        log.flush()
        process=subprocess.Popen(
            command,
            cwd=str(workdir),stdin=subprocess.DEVNULL,stdout=log,
            stderr=subprocess.STDOUT,close_fds=True,
            creationflags=creationflags)
    # The OS might reject startup due to a broken venv; do not report
    # fully initialized Whisper, only that the detached process was created.
    time.sleep(0.25)
    if process.poll() is not None:
        raise BackgroundLaunchError(
            f"HOVER terminó durante el arranque. Revisa {log_path}")
    tmp=pid_path.with_suffix(".pid.tmp")
    try:
        tmp.write_text(str(process.pid),encoding="ascii")
        os.replace(tmp,pid_path)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"HOVER iniciado en segundo plano (PID {process.pid}).",flush=True)
    print(f"Puedes cerrar PowerShell. Registro: {log_path}",flush=True)
    print("Para detenerlo ejecuta DETENER_HOVER.bat.",flush=True)
    return 0


def stop():
    pid=current_pid()
    path,_=state_paths()
    if pid is None:
        print("HOVER no aparece activo en segundo plano.",flush=True)
        return 0
    try:
        import psutil
        process=psutil.Process(pid)
        # The PID was verified against -m hover_next.app --voice; never kill
        # unrelated python.exe or PowerShell terminals.
        process.terminate()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            print("HOVER recibió la orden de cierre; aún se está cerrando.",
                  flush=True)
            return 1
    except (OSError,ValueError) as exc:
        raise BackgroundLaunchError("No pude detener HOVER.") from exc
    path.unlink(missing_ok=True)
    print("HOVER detenido; los demás terminales siguen intactos.",flush=True)
    return 0


def main():
    parser=argparse.ArgumentParser(description="Iniciar o detener HOVER sin consola")
    parser.add_argument("--stop",action="store_true")
    parser.add_argument("--engine",choices=("auto","parakeet","whisper"),
                        default="auto")
    parser.add_argument("--mic",type=int)
    parser.add_argument("--threshold",type=float)
    options=parser.parse_args()
    try:
        if options.stop:
            return stop()
        if options.threshold is not None and not 0<options.threshold<=1:
            raise BackgroundLaunchError("El umbral RMS está fuera de rango.")
        if options.mic is not None and not 0<=options.mic<=100:
            raise BackgroundLaunchError("Índice de micrófono inválido.")
        return start(engine=options.engine,mic=options.mic,
                     threshold=options.threshold)
    except BackgroundLaunchError as exc:
        print("HOVER:",exc,flush=True)
        return 1


if __name__=="__main__":
    raise SystemExit(main())

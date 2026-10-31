"""Local, no-network IPC between Windhawk Google buttons and HOVER Python.

The UI writes fixed allowlisted commands to %LOCALAPPDATA%\HOVER_NEXT.
It never receives OAuth tokens or passwords. Python's voice worker handles
consent so the 30ms mic callback never blocks on browser authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from . import google_auth

BASE=google_auth.BASE
CONTROL=BASE/"google_control.txt"
STATUS=BASE/"google_status.tsv"
VALID=re.compile(r"^(connect|disconnect)\s+(drive|gmail|calendar|docs|all)$")


def poll_control():
    if not CONTROL.is_file():
        return None
    try:
        # Remove as soon as read: no command replay after a restart.
        if CONTROL.stat().st_size>100:
            CONTROL.unlink(missing_ok=True)
            return None
        text=CONTROL.read_text(encoding="utf-8").strip()
        CONTROL.unlink(missing_ok=True)
        m=VALID.fullmatch(text)
        return (m.group(1),m.group(2)) if m else None
    except OSError:
        return None


def write_status(message=""):
    state=google_auth.status()
    values=["1" if state[key] else "0" for key in google_auth.SERVICES]
    safe=re.sub(r"[\t\r\n]"," ",message)[:135]
    BASE.mkdir(parents=True,exist_ok=True)
    temp=STATUS.with_suffix(".tmp")
    temp.write_text("\t".join(values+[safe]),encoding="utf-8")
    os.replace(temp,STATUS)


def execute_control(action,service):
    from .ui_bridge import publish
    if action not in ("connect","disconnect"):
        raise ValueError("Acción no admitida")
    if service!="all" and service not in google_auth.SERVICES:
        raise ValueError("Servicio no permitido")
    if action=="disconnect":
        message=google_auth.disconnect(service)
        write_status(message)
        publish("ok",message,3)
        return message
    services=google_auth.SERVICES if service=="all" else (service,)
    outcomes=[]
    for key in services:
        publish("thinking","Autorización de Google: "+key,3)
        write_status("Autoriza "+key+" en el navegador de Google")
        try:
            outcomes.append(google_auth.connect(key))
        except Exception as exc:
            # Do not print access tokens or raw Google HTTP responses.
            outcomes.append(f"{key}: {type(exc).__name__}. Revisa el archivo OAuth y la cuenta.")
        write_status(outcomes[-1])
    final="; ".join(outcomes)
    publish("ok",final[:110],3)
    return final

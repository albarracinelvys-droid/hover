"""Local, no-network IPC between Windhawk Google buttons and HOVER Python.

The UI writes fixed allowlisted commands to %LOCALAPPDATA%/HOVER_NEXT.
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
    # Detect missing Desktop OAuth configuration ONCE, before attempting
    # four authorizations and printing the same vague error four times.
    try:
        google_auth._client_path()
    except google_auth.GoogleAuthError:
        message=(
            "FALTA CLIENTE OAUTH: guarda google_oauth_client.json en "
            "%LOCALAPPDATA%/HOVER_NEXT. Configúralo en Google Cloud "
            "como aplicación de escritorio antes de pulsar Conectar.")
        print("[google]",message,flush=True)
        write_status(message)
        publish("error","Google: falta el archivo OAuth de escritorio",3)
        return message
    services=google_auth.SERVICES if service=="all" else (service,)
    outcomes=[]
    for key in services:
        publish("thinking","Autorización de Google: "+key,3)
        write_status("Autoriza "+key+" en el navegador de Google")
        try:
            # One account for all services: do not silently mix a work Drive
            # with someone else's personal Gmail.
            already=[k for k,active in google_auth.status().items()
                     if active and k!=key]
            existing_email=(google_auth.account_email(already[0]).casefold()
                            if already else "")
            google_auth.connect(key)
            try:
                new_email=google_auth.account_email(key).casefold()
            except Exception:
                # A token without verified account identity cannot be used
                # in an integration that promises one consistent account.
                google_auth.disconnect(key)
                raise google_auth.GoogleAuthError(
                    "Google no pudo verificar la identidad de esta cuenta.")
            if not new_email or (existing_email and new_email!=existing_email):
                google_auth.disconnect(key)
                raise google_auth.GoogleAuthError(
                    "La cuenta Google no coincide. Elige la misma cuenta en todos los servicios.")
            outcomes.append(key+" conectado como "+new_email)
        except Exception as exc:
            outcomes.append(f"{key}: {type(exc).__name__}. Comprueba el consentimiento, los permisos y las APIs.")
        write_status(outcomes[-1])
    final="; ".join(outcomes)
    publish("ok",final[:110],3)
    return final

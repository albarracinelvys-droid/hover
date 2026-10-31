"""One-click Windows Google OAuth setup for HOVER.

Use after updating HOVER: python -m hover_next.google_cli --service drive
All OAuth credentials stay on this PC and are encrypted with DPAPI.
"""
from __future__ import annotations

import argparse

from . import google_auth
from . import google_ipc


def _check_prerequisites():
    try:
        google_auth._client_path()
    except google_auth.GoogleAuthError as exc:
        print("ERROR CLIENTE OAUTH:",exc,flush=True)
        return False

    # Prove the local Windows DPAPI store works BEFORE opening Google.
    # The sample is not a credential and is never written to disk.
    try:
        probe=b"HOVER Windows DPAPI self-test"
        restored=google_auth._unprotect(google_auth._protect(probe))
        if restored!=probe:
            print("ERROR: Windows DPAPI no devolvio los datos correctos.",flush=True)
            return False
    except ImportError:
        print("ERROR: falta pywin32/win32crypt. Ejecuta INSTALAR_GOOGLE_HOVER.bat.",flush=True)
        return False
    except Exception as exc:
        print("ERROR DPAPI:",type(exc).__name__,flush=True)
        print("No se pudo comprobar el cifrado de Windows de esta cuenta.",flush=True)
        return False

    print("OK: JSON OAuth encontrado y cifrado Windows DPAPI operativo.",flush=True)
    return True


def _show_status():
    state=google_auth.status()
    for name in google_auth.SERVICES:
        print(f"{name}: {'SI' if state[name] else 'NO'}",flush=True)
    return state


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="Autorizar Google desde Python y comprobar token en HOVER")
    parser.add_argument("--service",choices=(*google_auth.SERVICES,"all"),
                        default="drive")
    parser.add_argument("--status",action="store_true")
    args=parser.parse_args(argv)

    if args.status:
        _show_status()
        return 0
    if not _check_prerequisites():
        return 2

    print("Abriendo Google. Completa los permisos en Chrome y REGRESA a esta consola.",flush=True)
    print("La pagina de retorno NO confirma por si sola que el token se haya guardado.",flush=True)
    try:
        result=google_ipc.execute_control("connect",args.service)
    except Exception as exc:
        # Do not print unsanitized OAuth exception messages: they could contain
        # an authorization URL/code. The IPC normally emits curated errors.
        print("ERROR DE CONEXION:",type(exc).__name__,flush=True)
        try:
            google_ipc.write_status("Google: fallo la conexion ("+type(exc).__name__+")")
        except OSError:
            pass
        return 1

    print("RESULTADO:",result,flush=True)
    state=_show_status()
    target=(google_auth.SERVICES if args.service=="all" else (args.service,))
    successful=all(
        state[key] and (key+" conectado como ") in result
        for key in target
    )
    if not successful:
        print("Google no quedo conectado. Revisa RESULTADO y google_status.tsv.",flush=True)
        return 1

    print("EXITO: autorizacion verificada y token cifrado guardado en Windows.",flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())

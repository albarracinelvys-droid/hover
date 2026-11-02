"""Use the Gmail account explicitly linked in HOVER to start ChatGPT login.

Google Workspace tokens and ChatGPT sessions are different. Google OAuth
tokens never leave the Google APIs: HOVER opens ChatGPT's official Google
sign-in in an isolated persistent Chrome profile. Human approval remains
necessary for Google password, challenge, MFA, and third-party consent.
"""
from __future__ import annotations

import re
import sys
from .executor import app_dir
from .browser import BrowserBridge,BrowserUnavailable


def linked_google_email():
    """Read the Gmail OAuth account *identity*, never its access token."""
    from . import google_auth
    if not google_auth.connected("gmail"):
        raise BrowserUnavailable(
            "Gmail no está vinculado en HOVER. Primero conecta Gmail en "
            "Atajos > Google o usando google_cli --service gmail."
        )
    try:
        email=google_auth.account_email("gmail").strip()
    except Exception as exc:
        raise BrowserUnavailable(
            "No pude verificar la identidad de tu Gmail vinculado. "
            "Vuelve a autorizar Gmail en HOVER si la sesión caducó."
        ) from exc
    if not re.fullmatch(r"[^@\s]{1,80}@[^@\s]{1,120}",email):
        raise BrowserUnavailable("El correo vinculado no es válido.")
    return email


def main():
    print("HOVER - Iniciar ChatGPT con la cuenta Google vinculada.")
    print("No se reutilizan tokens de Gmail ni se copian cookies/contraseñas.")
    print("Primero DETÉN HOVER: el Chrome automatizado usa un perfil exclusivo.")
    try:
        email=linked_google_email()
    except BrowserUnavailable as exc:
        print("Cuenta Google:",exc,flush=True)
        return 2
    print("Cuenta Gmail vinculada:",email,flush=True)
    bridge=BrowserBridge(app_dir()/"chrome_profile")
    try:
        page=bridge.page("chatgpt",new=True)
        stage=bridge.begin_google_sign_in(page,email)
        if stage=="selected":
            print("Seleccioné la cuenta Google coincidente en el selector visible.")
        elif stage=="google_opened":
            print("Continuar con Google abierto; selecciona tu cuenta "
                  "Gmail vinculada si aparece la lista.")
        else:
            print("Selecciona 'Continuar con Google' en ChatGPT. "
                  "Google puede solicitar autorización.")
        print("Completa cualquier contraseña, verificación o autorización "
              "manualmente EN CHROME. Nunca en esta terminal.")
        try:
            input("Después de comprobar tu cuenta de ChatGPT, pulsa Enter aquí: ")
        except EOFError:
            print("Se necesita PowerShell interactivo para terminar.",flush=True)
            return 2
        # This is not proof of which Google account ChatGPT selected;
        # verification of the signed-in ChatGPT identity is up to the user.
        if bridge._login_visible(page,"chatgpt"):
            print("ChatGPT aún muestra acceso pendiente en la pestaña original. "
                  "Verifica que Google terminó y que tu cuenta aparece en ChatGPT.")
            return 2
        print("Comprueba en ChatGPT > Configuración > Cuenta que el correo "
              "sea el Gmail esperado. Si coincide, la sesión de este perfil "
              "se conservará para las próximas órdenes de HOVER.")
        return 0
    except BrowserUnavailable as exc:
        print("No se pudo iniciar ChatGPT con Google:",exc,flush=True)
        return 2
    except Exception as exc:
        # Exceptions from Playwright can include URLs/OAuth query strings;
        # never print raw exception details.
        print("El navegador no completó el inicio de sesión:",
              type(exc).__name__,flush=True)
        return 2
    finally:
        bridge.close()


if __name__=="__main__":
    sys.exit(main())

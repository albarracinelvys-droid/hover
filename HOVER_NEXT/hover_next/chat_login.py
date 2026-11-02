"""One-time interactive account sign-in for HOVER's isolated Chrome profile.

OAuth cookies/passwords are handled only by the provider in Chrome, not Python.
HOVER never reads or imports the signed-in user's main Chrome profile.
Run only when the background voice engine is stopped; Chrome locks profiles.
"""
from __future__ import annotations

import sys
from .executor import app_dir
from .browser import BrowserBridge,BrowserUnavailable


def main():
    bridge=BrowserBridge(app_dir()/"chrome_profile")
    print("HOVER - Vincular ChatGPT en Chrome controlado por HOVER.")
    print("El perfil es independiente de tu Chrome habitual.")
    print("Detén HOVER antes de conectar para evitar dos procesos con ese perfil.")
    print("Inicia sesión manualmente con la cuenta que quieras usar.")
    print("No escribas ni compartas contraseñas en esta consola.")
    try:
        page=bridge.page("chatgpt",new=True)
        print("Chrome abierto en",page.url)
        try:
            input("Cuando veas tu cuenta iniciada en ChatGPT, pulsa Enter aquí: ")
        except EOFError:
            print("Requiere una consola interactiva para confirmar el inicio de sesión.")
            return 2
        # Authentication identity is private and cannot be inferred from
        # a missing login button. Only report that the login UI disappeared.
        if bridge._login_visible(page,"chatgpt"):
            print("Aún aparece la pantalla de inicio de sesión.")
            return 2
        print("No se detecta pantalla de login. Comprueba tu avatar/correo "
              "en el Chrome abierto. La sesión de este perfil se conservará.")
        return 0
    except BrowserUnavailable as exc:
        print("No se pudo abrir Chrome:",exc)
        return 2
    finally:
        bridge.close()


if __name__=="__main__":
    sys.exit(main())

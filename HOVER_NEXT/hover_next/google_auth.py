"""HOVER Google OAuth 2.0 for an installed Windows desktop app.

Tokens are encrypted with Windows DPAPI (CurrentUser), not stored as JSON.
Each service has independent least-privilege consent and disconnect.
Never logs credentials, authorization codes, token contents, or OAuth URLs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

BASE = Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "HOVER_NEXT"
CLIENT = BASE / "google_oauth_client.json"  # user-supplied Desktop OAuth JSON
TOKEN_FOLDER = BASE / "google_tokens"
SERVICES = ("drive","calendar","gmail","docs")

SCOPES = {
    "drive": (
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ),
    "calendar": (
        "https://www.googleapis.com/auth/calendar.events",
    ),
    "gmail": (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ),
    "docs": (
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.file",
    ),
}
# Google may return the OpenID identity aliases "openid" and "email" along
# with userinfo.email. Request them explicitly: oauthlib validates that
# the scopes in the token response match the scopes requested.
IDENTITY_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/userinfo.email",
)


def _requested_scopes(service):
    return list(SCOPES[_validate_service(service)]) + list(IDENTITY_SCOPES)


def _scope_set(value):
    """Normalize oauthlib's scope list/string without exposing token data."""
    if isinstance(value,str):
        return set(value.split())
    if isinstance(value,(list,tuple,set,frozenset)) and all(
        isinstance(x,str) for x in value
    ):
        return set(value)
    return set()


def _permit_google_identity_aliases(flow, service):
    """Only tolerate Google's harmless identity-scope normalization.

    OAuthlib rejects *any* scope mismatch. Google may omit/replace the
    redundant OpenID aliases even when the protected API scope is present.
    Install an adapter on this OAuth client instance; never relax scope checks
    for other sessions or accept missing API permissions.
    """
    oauth_client=flow.oauth2session._client
    original=oauth_client.parse_request_body_response
    required=set(SCOPES[service])
    requested=set(_requested_scopes(service))
    identity={"email","https://www.googleapis.com/auth/userinfo.email"}

    def parse_google_response(body,scope=None,**kwargs):
        try:
            return original(body,scope=scope,**kwargs)
        except Warning as mismatch:
            previous=_scope_set(getattr(mismatch,"old_scope",None))
            granted=_scope_set(getattr(mismatch,"new_scope",None))
            token=getattr(mismatch,"token",None)
            # Reject unrelated warnings, added privileges and denied API
            # permissions. The original OAuth transaction still validates
            # authorization-code state, redirect URI, PKCE and token response.
            if (previous != requested
                or not required.issubset(granted)
                or not granted.intersection(identity)
                or not granted.issubset(requested)
                or not isinstance(token,dict)
                or not token.get("access_token")
                or token.get("token_type","").casefold()!="bearer"):
                raise GoogleAuthError(
                    "Google cambió permisos esenciales o devolvió permisos "
                    "inesperados. No se guardó ningún token."
                ) from mismatch
            # This warning occurs AFTER oauthlib validates the token body.
            # Finish the same per-session parser's assignment, which was
            # interrupted by the warning; keep oauthlib expiration checks.
            oauth_client.token=token
            oauth_client.populate_token_attributes(token)
            return token

    oauth_client.parse_request_body_response=parse_google_response


class GoogleAuthError(RuntimeError):
    pass


def _validate_service(service):
    if service not in SERVICES:
        raise ValueError("Servicio de Google no permitido.")
    return service


def _token_path(service):
    return TOKEN_FOLDER / (_validate_service(service)+".dpapi")


def _protect(plaintext: bytes) -> bytes:
    if sys.platform != "win32":
        raise GoogleAuthError("Los tokens Google requieren Windows DPAPI.")
    import win32crypt
    return win32crypt.CryptProtectData(plaintext,"HOVER Google OAuth",None,None,None,0)


def _unprotect(ciphertext: bytes) -> bytes:
    if sys.platform != "win32":
        raise GoogleAuthError("Los tokens Google requieren Windows DPAPI.")
    import win32crypt
    return win32crypt.CryptUnprotectData(ciphertext,None,None,None,0)[1]


def _save(service, credentials):
    TOKEN_FOLDER.mkdir(parents=True,exist_ok=True)
    target=_token_path(service)
    data=_protect(credentials.to_json().encode("utf-8"))
    # Never persist unencrypted tokens even as a temporary file.
    with tempfile.NamedTemporaryFile(mode="wb",dir=TOKEN_FOLDER,
                                     prefix=".oauth-",suffix=".tmp",
                                     delete=False) as handle:
        temp=Path(handle.name)
        handle.write(data)
    try:
        os.replace(temp,target)
    finally:
        temp.unlink(missing_ok=True)


def _read(service):
    target=_token_path(service)
    if not target.is_file():
        return None
    try:
        from google.oauth2.credentials import Credentials
        blob=_unprotect(target.read_bytes())
        # Require the service's own scopes; never reuse another service's
        # broader token or mistake a service for having been authorized.
        cred=Credentials.from_authorized_user_info(
            json.loads(blob),scopes=_requested_scopes(service))
        return cred
    except (OSError,UnicodeError,ValueError,KeyError) as exc:
        raise GoogleAuthError(
            f"El token de {service} no se puede descifrar. "
            "Desconecta ese servicio y vuelve a autorizarlo."
        ) from exc


def _client_path():
    if not CLIENT.is_file():
        raise GoogleAuthError(
            "Falta google_oauth_client.json en %LOCALAPPDATA%\\HOVER_NEXT. "
            "Descarga un cliente OAuth de tipo Aplicación de escritorio "
            "desde Google Cloud y guárdalo allí; jamás en GitHub."
        )
    try:
        obj=json.loads(CLIENT.read_text(encoding="utf-8"))
        installed=obj.get("installed")
        if not isinstance(installed,dict) or not installed.get("client_id"):
            raise ValueError("No es una credencial OAuth tipo Desktop")
        return CLIENT
    except (OSError,ValueError) as exc:
        raise GoogleAuthError("El archivo OAuth de escritorio no es válido.") from exc


def connect(service):
    """Complete OAuth, then persist an encrypted token before reporting success."""
    _validate_service(service)
    _client_path()
    if sys.platform!="win32":
        raise GoogleAuthError("La conexión desde la isla se realiza en Windows.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthError(
            "Falta google-auth-oauthlib. Ejecuta INSTALAR_GOOGLE_HOVER.bat."
        ) from exc

    try:
        flow=InstalledAppFlow.from_client_secrets_file(
            str(CLIENT),scopes=_requested_scopes(service))
        # The returned identity aliases can vary between Google's consent
        # screen and token endpoint; handle only the proven safe variants.
        # Mock flows used in unit tests do not expose an oauthlib client.
        if hasattr(flow.oauth2session,"_client"):
            _permit_google_identity_aliases(flow,service)
        # Google's redirect page appears BEFORE the token exchange and save.
        # Never claim the account is connected on that intermediate page.
        credentials=flow.run_local_server(
            host="127.0.0.1",port=0,open_browser=True,
            authorization_prompt_message="Autoriza HOVER en la pestaña de Google.",
            success_message=(
                "Permisos recibidos. Vuelve a HOVER para comprobar "
                "que la conexión se haya guardado."),
            access_type="offline",prompt="consent")
    except GoogleAuthError:
        raise
    except Exception as exc:
        if "Scope has changed" in str(exc):
            raise GoogleAuthError(
                "Google devolvió permisos distintos, que no corresponden "
                "a las variantes de identidad permitidas."
            ) from exc
        raise GoogleAuthError(
            f"Falló el intercambio OAuth de {service} "
            f"({type(exc).__name__}). Comprueba la autorización en Google."
        ) from exc

    try:
        _save(service,credentials)
    except ImportError as exc:
        raise GoogleAuthError(
            "Google autorizó la cuenta, pero no se pudo cifrar el token: "
            "falta pywin32/win32crypt. Ejecuta INSTALAR_GOOGLE_HOVER.bat."
        ) from exc
    except (OSError,GoogleAuthError) as exc:
        raise GoogleAuthError(
            f"Google autorizó la cuenta, pero Windows no pudo guardar el "
            f"token cifrado de {service} ({type(exc).__name__})."
        ) from exc
    except Exception as exc:
        raise GoogleAuthError(
            f"Google autorizó la cuenta, pero falló el guardado DPAPI de "
            f"{service} ({type(exc).__name__})."
        ) from exc

    if not _token_path(service).is_file():
        raise GoogleAuthError(
            f"No se encontró el token cifrado de {service} tras autorizar."
        )
    return f"{service} conectado mediante OAuth 2.0"


def credentials(service):
    _validate_service(service)
    cred=_read(service)
    if cred is None:
        raise GoogleAuthError(
            f"{service} no conectado. Abre Atajos > Google > Conectar {service}.")
    if not cred.valid:
        if not cred.refresh_token:
            raise GoogleAuthError(
                f"Google solicitó reconectar {service}.")
        try:
            from google.auth.transport.requests import Request
            cred.refresh(Request())
            _save(service,cred)
        except Exception as exc:
            raise GoogleAuthError(
                f"No se pudo renovar {service}; vuelve a conectarlo.") from exc
    return cred


def connected(service):
    return _token_path(service).is_file()


def status():
    return {key:connected(key) for key in SERVICES}


def disconnect(service="all"):
    targets=SERVICES if service=="all" else (_validate_service(service),)
    for key in targets:
        # Local disconnect is immediate. Remote authorization can also be
        # revoked at https://myaccount.google.com/permissions .
        _token_path(key).unlink(missing_ok=True)
    return "Google desconectado localmente: "+", ".join(targets)


def account_email(service):
    """Fetch the address only when status UI requests it, without caching it."""
    import requests
    cred=credentials(service)
    reply=requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization":"Bearer "+cred.token},timeout=12)
    reply.raise_for_status()
    return str(reply.json().get("email",""))[:120]

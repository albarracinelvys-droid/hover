"""Explicit, allowlisted Windows actions. No LLM-generated shell commands."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from .intent import Intent
from .browser import BrowserBridge, URLS

def app_dir():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'HOVER_NEXT'

def load_config(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}

def find_download(name: str, downloads: Path):
    if not downloads.exists(): raise FileNotFoundError(f'No existe la carpeta: {downloads}')
    candidates=[p for p in downloads.iterdir() if p.is_file() and not p.name.startswith('.') and not p.name.endswith(('.crdownload','.part','.tmp'))]
    if name:
        matches=[p for p in candidates if name.casefold() in p.name.casefold()]
        if not matches: raise FileNotFoundError(f'No encuentro {name!r} en Descargas')
        candidates=matches
    if not candidates: raise FileNotFoundError('No encuentro archivos descargados')
    return max(candidates,key=lambda p:p.stat().st_mtime)

def safe_destination(source: Path, folder: Path):
    folder.mkdir(parents=True,exist_ok=True)
    destination=folder/source.name
    index=2
    while destination.exists():
        destination=folder/f'{source.stem} ({index}){source.suffix}';index+=1
    return destination

def confirm_intent(intent: Intent) -> bool:
    if not intent.requires_confirmation:
        return True
    print(f'CONFIRMACION: {intent.action} {intent.provider} {intent.args}', flush=True)
    # Repos are permanent GitHub objects. Confirm the exact transcribed name,
    # never only "SI": Whisper sometimes changes a proper name.
    if intent.action == 'create_private_repo':
        name = intent.args.get('name','')
        typed = input(f'Para crear el repositorio PRIVADO escribe exactamente {name}: ').strip()
        return typed == name
    return input('¿Ejecutar esta accion? escribe SI: ').strip().upper()=='SI'

class Executor:
    def __init__(self, config_path: Path | None = None, browser: BrowserBridge | None = None):
        self.path=config_path or app_dir() / 'config.json'
        self.config=load_config(self.path)
        self.downloads=Path(self.config.get('downloads', str(Path.home()/'Downloads')))
        self.folder=Path(self.config['folder']).expanduser() if self.config.get('folder') else None
        self.browser=browser or BrowserBridge(app_dir() / 'chrome_profile')
    def execute(self,intent: Intent,confirmed: bool=False):
        if intent.action=='unknown':
            return 'No entendi la accion; no hice cambios.'
        if intent.requires_confirmation and not confirmed:
            return 'Accion pendiente de confirmacion. No se ejecuto.'
        action=intent.action
        provider=intent.provider
        if action == 'show_help':
            return ('Comandos: calculadora, Word, Excel, GitHub, WhatsApp, Google, '
                    'Drive, Gmail, Descargas, Administrador de tareas, volumen, '
                    'musica y repositorios privados (requieren confirmacion).')
        if action == 'media_key':
            from .desktop import send_media_key
            return send_media_key(intent.args['key'])
        if action == 'google_search':
            from .desktop import search_google
            return search_google(intent.args['query'])
        if action == 'search_query_needed':
            return 'Repite la busqueda con un termino claro. Ejemplo: Hover busca iPhone en Google.'
        if action == 'repo_name_needed':
            return ('Entendí que quieres crear un repositorio privado, pero no su nombre. '
                    'Di: Hover, crea un repositorio privado en GitHub llamado Ejemplo.')
        if action == "open_link":
            from .desktop import open_site_shortcut
            return open_site_shortcut(intent.args["site"])
        if action == "close_google_tab":
            from .desktop import close_google_tab
            return close_google_tab()
        if action == "windows_app":
            from .desktop import open_windows_app
            return open_windows_app(intent.args["app"])
        if action == "office_new":
            from .desktop import new_office_document
            return new_office_document(intent.args["kind"])
        if action == "open_document":
            from .desktop import open_document
            return open_document(intent.args.get("name", ""))
        if action == "google_app":
            from .desktop import open_google
            return open_google(intent.args["service"])
        if action in ("chat_prepare", "chat_compose"):
            project = intent.args.get("project", "").casefold()
            project_url = ""
            if project:
                from .projects import get_project_url
                project_url = get_project_url(self.config, provider, project)
                if not project_url:
                    raise ValueError(
                        f"Configura primero la URL real del proyecto {project} de {provider}. "
                        "No abrí un chat general por error."
                    )
            result = self.browser.prepare_chat(provider, project_url)
            if action == "chat_compose":
                result = self.browser.send_prepared(provider, intent.args.get("prompt", ""))
            return result
        if action == "chat_send_prepared":
            return self.browser.send_prepared(provider, intent.args.get("prompt", ""))
        if action in ('agent_ask','agent_task'):
            from .agent import run_agent
            return run_agent(intent.args.get('prompt',''),self.config,write=action=='agent_task')
        if action=='show_pc':
            subprocess.Popen(['explorer.exe','shell:MyComputerFolder'])
            return 'Abriendo Este equipo.'
        if action=='screenshot':
            if sys.platform!='win32': return 'La captura requiere Windows.'
            import ctypes
            user32=ctypes.windll.user32
            for key in [0x5B,0x10,0x53]:user32.keybd_event(key,0,0,0)
            for key in [0x53,0x10,0x5B]:user32.keybd_event(key,0,2,0)
            return 'Herramienta de recorte activada.'
        if action=='spotify_play':
            webbrowser.open('spotify:')
            return 'Abri Spotify. La reproduccion necesita una sesion multimedia activa; no la he confirmado.'
        if action=='open_site':
            # Simple Siri-style open: use the existing default browser and session.
            # Playwright is reserved for composing and uploading files.
            from .browser import URLS
            url = URLS.get(provider)
            if not url:
                raise ValueError("No se reconoce el proveedor web")
            opened = webbrowser.open_new_tab(url)
            if not opened:
                raise RuntimeError("Windows no pudo abrir el navegador predeterminado.")
            return f'Abriendo {provider} en tu navegador.'
        if action=='new_chat':
            self.browser.page(provider,new=True)
            return f'Abriendo nueva conversacion en {provider}.'
        if action=='open_project':
            name=intent.args.get('name','').strip().casefold()
            from .projects import get_project_url
            url = get_project_url(self.config,provider,name) if name else ""
            if not url:
                return f'No tengo la URL del proyecto {name!r} en {provider}; añadela desde Atajos en HOVER.'
            return self.browser.open_project(provider,url)
        if action=='close_tab':
            self.browser.close_tab(provider)
            return f'Cerrada la ultima pestana de {provider} controlada por HOVER.'
        if action in ('send_prompt','new_chat_and_send'):
            return self.browser.send_prompt(provider,intent.args['prompt'],new=(action=='new_chat_and_send'))
        if action=='upload_file':
            if provider not in ('chatgpt','claude'):return 'Indica ChatGPT o Claude.'
            name=intent.args.get('filename','')
            if not name:return 'Indica el nombre de un archivo de Descargas para evitar adjuntar uno incorrecto.'
            file=find_download(name,self.downloads)
            return self.browser.send_prompt(provider,intent.args.get('prompt',''),file=file)
        if action in ('copy_latest_download','move_latest_download'):
            if not self.folder:return 'Configura folder en config.json.'
            source=find_download('',self.downloads)
            dest=safe_destination(source,self.folder)
            if action=='copy_latest_download':
                shutil.copy2(source,dest)
            else:
                shutil.move(str(source),str(dest))
            return f'Archivo {source.name} {"copiado" if action.startswith("copy") else "movido"} a {dest}'
        if action=='create_private_repo':
            name=intent.args['name']
            if not re.fullmatch(r'[a-zA-Z0-9._-]{1,100}',name):return 'Nombre invalido.'
            exe=shutil.which('gh')
            if not exe:return ('GitHub CLI no está instalado. En PowerShell: '
                               'winget install --id GitHub.cli -e; después gh auth login.')
            r=subprocess.run([exe,'repo','create',name,'--private','--description','Repositorio creado con HOVER'],capture_output=True,text=True,timeout=45)
            if r.returncode:raise RuntimeError((r.stderr or r.stdout).strip())
            return (r.stdout or f'Repositorio privado {name} creado').strip()
        return 'Accion no implementada.'

"""Local Chrome automation; user signs into an isolated, personal browser profile."""
from __future__ import annotations
from pathlib import Path

URLS={'chatgpt':'https://chatgpt.com/','claude':'https://claude.ai/new'}
HOSTS={'chatgpt':('chatgpt.com','chat.openai.com'),'claude':('claude.ai',)}

class BrowserUnavailable(RuntimeError):
    pass

class BrowserBridge:
    def __init__(self, profile: Path):
        self.profile=profile
        self.p=None
        self.context=None
        self.prepared=None
    def _ensure(self):
        if self.context: return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise BrowserUnavailable('Instala Playwright: pip install playwright') from e
        print("[chat] Abriendo Chrome controlado por HOVER (perfil independiente).",flush=True)
        print("[chat] Si no has entrado, inicia sesión en ESTE Chrome una sola vez.",flush=True)
        self.p=sync_playwright().start()
        try:
            self.context=self.p.chromium.launch_persistent_context(
                str(self.profile),channel='chrome',headless=False,accept_downloads=True)
        except Exception as e:
            self.p.stop();self.p=None
            raise BrowserUnavailable('No pude iniciar Chrome. Comprueba que esta instalado y no uses dos HOVER simultaneos.') from e
    def _tabs(self,provider):
        hosts=HOSTS[provider]
        return [p for p in self.context.pages if any((p.url.split('/')[2].split(':')[0] if '://' in p.url else '')==h for h in hosts)]
    def page(self,provider, new=False):
        if provider not in URLS: raise ValueError('Proveedor no permitido')
        self._ensure()
        if not new:
            matches=self._tabs(provider)
            if matches: return matches[-1]
        page=self.context.new_page()
        page.goto(URLS[provider],wait_until='domcontentloaded',timeout=30000)
        return page
    def open_project(self,provider,url):
        if not url: raise ValueError('Configura primero la URL exacta del proyecto en config.json')
        from urllib.parse import urlparse
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in HOSTS[provider]:
            raise ValueError('La URL no coincide con el proveedor elegido')
        page=self.page(provider)
        page.goto(url,wait_until='domcontentloaded',timeout=30000)
        return page.url
    def close_tab(self,provider):
        self._ensure()
        matched=self._tabs(provider)
        if not matched: raise BrowserUnavailable(f'No hay pestaña de {provider} abierta bajo HOVER')
        matched[-1].close();return True
    def send_prompt(self,provider,prompt,file=None,new=False):
        page=self.page(provider,new=new)
        if file:
            chooser=page.locator('input[type="file"]').first
            if chooser.count()==0:
                raise BrowserUnavailable('No encontre el campo de adjuntos. Abre el chat e inserta el archivo manualmente.')
            chooser.set_input_files(str(file),timeout=10000)
        if prompt:
            selectors=['[contenteditable="true"][role="textbox"]','div[contenteditable="true"]','textarea']
            editor=None
            for s in selectors:
                loc=page.locator(s).last
                if loc.count(): editor=loc;break
            if editor is None: raise BrowserUnavailable('No encontre el cuadro de texto: inicia sesion y abre un chat.')
            editor.fill(prompt,timeout=10000)
            editor.press('Enter')
        return 'Enviado al navegador; comprueba la respuesta en la pagina.'
    def prepare_chat(self, provider, project_url=""):
        """Opens a separate browser tab for a new conversation.

        For a project, this uses the exact configured project page. We never
        fall back to a generic ChatGPT chat if the project cannot be opened.
        """
        from urllib.parse import urlparse
        if provider not in URLS:
            raise ValueError("ChatGPT o Claude no reconocido.")
        self._ensure()
        if project_url:
            address = urlparse(project_url)
            if address.scheme != "https" or address.hostname not in HOSTS[provider]:
                raise ValueError("La URL del proyecto no corresponde al proveedor solicitado.")
            if provider == "chatgpt" and "/g/g-p-" not in address.path:
                raise ValueError("La URL no parece ser de un proyecto de ChatGPT. Copia la URL del proyecto, no de un chat individual.")
            page = self.context.new_page()
            page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
            # The project page is the only allowed target here.
            # The browser will not silently fall back to a general chat.

        else:
            page = self.page(provider, new=True)
        page.bring_to_front()
        self.prepared = (provider, page)
        print(f"[chat] Chat preparado: {provider}. Buscando el cuadro de escritura.",flush=True)
        return "Pestaña abierta. Dicta el mensaje."

    def send_prepared(self, provider, prompt):
        if not prompt or not prompt.strip():
            raise ValueError("No hay texto para dictar.")
        if self.prepared is None or self.prepared[0] != provider:
            raise BrowserUnavailable("Primero abre el chat o proyecto con HOVER.")
        page = self.prepared[1]
        if page.is_closed():
            raise BrowserUnavailable("El chat preparado se cerró.")
        # Never enter the prompt in a redirected login page or unrelated tab.
        from urllib.parse import urlparse
        hostname = urlparse(page.url).hostname
        if hostname not in HOSTS[provider]:
            raise BrowserUnavailable(
                "HOVER te llevó a una pantalla de inicio de sesión. "
                "Accede a tu cuenta en el Chrome abierto por HOVER y repite la orden."
            )
        selectors = {
            "chatgpt": ["#prompt-textarea",
                        '[contenteditable="true"][role="textbox"]',
                        'div[contenteditable="true"]', 'textarea'],
            "claude": ['div.ProseMirror[contenteditable="true"]',
                       '[contenteditable="true"][role="textbox"]',
                       'div[contenteditable="true"]', 'textarea'],
        }[provider]
        editor = None
        for selector in selectors:
            locator = page.locator(selector).last
            if locator.count() and locator.is_visible():
                editor = locator
                break
        if editor is None:
            raise BrowserUnavailable(
                "No encontré el cuadro del mensaje. HOVER utiliza un Chrome "
                "independiente: inicia sesión allí, entra al chat correcto "
                "y repite tu orden de voz."
            )
        page.bring_to_front()
        print(f"[chat] Escribiendo en {provider}: {prompt[:90]!r}",flush=True)
        editor.fill(prompt, timeout=10000)
        editor.press("Enter", timeout=10000)
        print("[chat] Pulsé Enter en el cuadro del chat.",flush=True)
        self.prepared = None
        return ("Escribí el mensaje y pulsé Enter en el chat; "
                "verifica que aparezca enviado en el navegador.")

    def close(self):
        self.prepared=None
        if self.context:self.context.close();self.context=None
        if self.p:self.p.stop();self.p=None

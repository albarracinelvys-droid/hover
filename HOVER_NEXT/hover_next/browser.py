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
    def _ensure(self):
        if self.context: return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise BrowserUnavailable('Instala Playwright: pip install playwright') from e
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
    def close(self):
        if self.context:self.context.close();self.context=None
        if self.p:self.p.stop();self.p=None

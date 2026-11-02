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
        """Send the spoken prompt without a second approval or misleading status.

        The normal prompt path uses the SAME verified editor as chat_compose.
        A separately selected file may also be attached, but does not bypass
        the privacy confirmation enforced by the intent parser.
        """
        page=self.page(provider,new=new)
        if file:
            chooser=page.locator('input[type="file"]').first
            if chooser.count()==0:
                raise BrowserUnavailable(
                    'No encontré el campo de adjuntos. Abre el chat e inserta el archivo manualmente.')
            chooser.set_input_files(str(file),timeout=10000)
        if prompt and prompt.strip():
            self.prepared=(provider,page)
            return self.send_prepared(provider,prompt)
        if file:
            return ('Archivo seleccionado en el navegador, pero no se envió '
                    'ningún mensaje; comprueba el adjunto antes de continuar.')
        raise ValueError("No hay texto para enviar al chat.")

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
        if self._login_visible(page,provider):
            if provider=="chatgpt":
                try:
                    from .google_auth import account_email,connected
                    if connected("gmail"):
                        linked=account_email("gmail")
                        stage=self.begin_google_sign_in(page,linked)
                        print("[chat] Acceso con Google vinculado:",stage,flush=True)
                        return ("Abrí el inicio de sesión de ChatGPT con Google. "
                                "Confirma tu cuenta vinculada en Chrome si Google "
                                "lo solicita y después repite la orden de voz.")
                except Exception as exc:
                    print("[chat] Google vinculado no pudo iniciar acceso:",
                          type(exc).__name__,flush=True)
            print("[chat] Falta iniciar sesión en el perfil independiente de HOVER.",
                  flush=True)
            return ("ChatGPT requiere iniciar sesión en el Chrome de HOVER. "
                    "Ejecuta CONECTAR_CHATGPT.bat para usar tu Google vinculado.")
        print(f"[chat] Chat preparado: {provider}. Buscando el cuadro de escritura.",flush=True)
        return "Chat preparado en "+provider+". Dicta el mensaje."

    def begin_google_sign_in(self, page, linked_email):
        """Start official ChatGPT -> Google sign-in in HOVER's Chrome.

        HOVER never exchanges its Google Workspace OAuth tokens with ChatGPT,
        copies cookies, enters passwords, or accepts consent on the user's
        behalf. It may choose an already visible *exact* linked Google account.
        User completes any Google verification/consent manually.
        """
        import re
        from urllib.parse import urlparse
        if not re.fullmatch(r"[^@\s]{1,80}@[^@\s]{1,120}",linked_email or ""):
            raise BrowserUnavailable("No se pudo verificar el Gmail vinculado.")
        page.goto("https://chatgpt.com/auth/login",
                  wait_until="domcontentloaded",timeout=30000)
        # ChatGPT may redirect a previously authenticated profile back home.
        if urlparse(page.url).hostname not in (*HOSTS["chatgpt"],
                                               "auth.openai.com"):
            raise BrowserUnavailable("Redirección fuera del inicio de sesión oficial de ChatGPT.")
        pattern=re.compile(r"(?:continuar|iniciar sesi[oó]n|acceder|entrar|"
                           r"continue|sign in|log in)\s+(?:con|with)\s+google",
                           re.IGNORECASE)
        found=None
        for role in ("button","link"):
            button=page.get_by_role(role,name=pattern).first
            if button.count() and button.is_visible():
                found=button
                break
        if found is None:
            # The user can still select Google's entry manually; do not
            # guess hidden links or navigate to an invented Google OAuth URL.
            return "manual"
        found.click(timeout=6000)
        print("[chat] Se abrió Continuar con Google.",flush=True)
        # Google might use an inline redirect or an account-chooser popup.
        # A fixed small wait is confined to the one-time sign-in path.
        page.wait_for_timeout(650)
        pages=list(self.context.pages) if self.context else [page]
        if page not in pages:
            pages.append(page)
        for google_page in reversed(pages):
            if urlparse(google_page.url).hostname!="accounts.google.com":
                continue
            account=google_page.get_by_text(linked_email,exact=True).first
            if account.count() and account.is_visible():
                account.click(timeout=5000)
                print("[chat] Se seleccionó la cuenta Google vinculada; "
                      "completa cualquier confirmación en Chrome.",flush=True)
                return "selected"
        return "google_opened"

    def _login_visible(self, page, provider):
        """Detect known authentication screens; fail closed for obvious logout.

        The host may remain chatgpt.com while showing login/guest UI, so
        checking only the URL is insufficient.
        """
        from urllib.parse import urlparse
        url=urlparse(page.url)
        if url.hostname not in HOSTS[provider]:
            return True
        if "/auth/login" in url.path or "/login" in url.path:
            return True
        selectors=(
            'a[href*="/auth/login"]',
            'button[data-testid="login-button"]',
            'a[data-testid="login-button"]',
        ) if provider=="chatgpt" else (
            'a[href*="/login"]', 'a[href*="/auth/login"]',
        )
        for selector in selectors:
            item=page.locator(selector).first
            if item.count() and item.is_visible():
                return True
        return False

    def _message_delivered(self,page,provider,prompt,before=0):
        """Wait for a *new* user message in DOM; Enter alone is not delivery."""
        selectors={
            "chatgpt":'[data-message-author-role="user"]',
            "claude":'[data-testid="user-message"]',
        }
        selector=selectors[provider]
        try:
            # Passing args separately avoids injecting dictation into JS.
            # The previous implementation only waited for an *old* message
            # to remain visible; that did not confirm a new submission.
            page.wait_for_function(
                """({selector, previous, text}) => {
                    const nodes = [...document.querySelectorAll(selector)];
                    if (nodes.length <= previous) return false;
                    const normalize = s => String(s).replace(/\\s+/g,' ').trim();
                    return normalize(nodes[nodes.length - 1].innerText)
                           .includes(normalize(text));
                }""",
                arg={"selector":selector,"previous":before,"text":prompt},
                timeout=4500)
            return True
        except Exception:
            return False

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
        if self._login_visible(page,provider):
            raise BrowserUnavailable(
                "ChatGPT/Claude está mostrando el inicio de sesión en el "
                "Chrome independiente de HOVER. Inicia sesión en esa ventana "
                "con tu cuenta, vuelve al chat y repite la instrucción. "
                "HOVER no puede importar la sesión privada de Chrome principal."
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
        selector=('chatgpt' if provider=='chatgpt' else 'claude')
        existing=(page.locator('[data-message-author-role="user"]').count()
                  if provider=='chatgpt' else
                  page.locator('[data-testid="user-message"]').count())
        print(f"[chat] Preparando texto para {provider} ({len(prompt)} caracteres).",
              flush=True)
        editor.fill(prompt, timeout=10000)
        editor.press("Enter", timeout=10000)
        if not self._message_delivered(page,selector,prompt,before=existing):
            # Keep the prepared session so the user can inspect/resend without
            # silently duplicating a message. Do not claim it was sent.
            raise BrowserUnavailable(
                "El navegador recibió Enter, pero HOVER NO confirmó un mensaje "
                "de usuario enviado. Revisa la sesión iniciada y el chat. "
                "El texto puede seguir en el editor; no lo reenviaré solo."
            )
        print("[chat] Mensaje de usuario confirmado en el chat.",flush=True)
        self.prepared = None
        return "Mensaje confirmado en la conversación de "+provider+"."

    def close(self):
        """Idempotent cleanup; called by the browser's owning thread only."""
        self.prepared=None
        context,self.context=self.context,None
        playwright,self.p=self.p,None
        if context is not None:
            try:
                context.close()
            except Exception as exc:
                # Chrome may already have been closed by the user.
                print("[chat] Chrome ya estaba cerrado:",type(exc).__name__,flush=True)
        if playwright is not None:
            try:
                playwright.stop()
            except Exception as exc:
                print("[chat] Playwright ya estaba detenido:",type(exc).__name__,flush=True)

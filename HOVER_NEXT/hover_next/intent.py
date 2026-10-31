"""Rule-based, conservative intent parser. Never generates shell commands."""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import unicodedata
from .wake import extract_wake


@dataclass(frozen=True)
class Intent:
    action: str
    provider: str = ""
    args: dict[str, str] = field(default_factory=dict)
    requires_confirmation: bool = False


def normalize(s: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFKD', s.casefold()) if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip(' \t\n\r.!?¿¡')


def identify_provider(t: str) -> str:
    if re.search(r'\b(chat\s*gpt|chatgpt|chat\s*gepete|chat\s*e\s*pepe|cati\s*petit)\b', t):
        return 'chatgpt'
    if re.search(r'\b(claude|cloud|clau|clout|clouding|clod|cloude)\b', t):
        return 'claude'
    if re.search(r'\b(spotify|spotifai|espotifai)\b', t):
        return 'spotify'
    return ''


def _parse_private_repo_request(t: str) -> Intent | None:
    """Safely interpret voice requests for private GitHub repositories.

    A known ASR substitution, 'seria uno de los requisitorios', is accepted
    ONLY with 'privado' and an explicit name. Creation always requires
    confirming the exact slug in the terminal; it is never automatic.
    """
    repository = r'(?:repo(?:sitorio)?s?|requisitori[oa]s?)'
    if not re.search(r'\b' + repository + r'\b', t):
        return None
    if not re.search(r'\bprivad[oa]s?\b', t):
        return None
    creation = re.search(r'\b(?:crea|crear|creame|genera|generar)\b', t)
    misheard_creation = re.search(
        r'\bseria\s+uno\s+de\s+los\s+' + repository + r'\b', t)
    if not creation and not misheard_creation:
        return None
    marker = re.search(
        r'\b(?:que\s+se\s+llam(?:a|e)|llamad[oa]|'
        r'con\s+el\s+nombre\s+de|nombre(?:\s+de)?)\s+(.+)$', t)
    if not marker:
        return Intent('repo_name_needed')
    raw_name = marker.group(1).strip(' \t.,;!?:')
    words = raw_name.split()
    # Restrict to simple, short names; never silently truncate the user's name.
    if not 1 <= len(words) <= 4:
        return Intent('repo_name_needed')
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]*', word) for word in words):
        return Intent('repo_name_needed')
    name = '-'.join(words).strip('.-')
    if len(name) < 2 or len(name) > 100:
        return Intent('repo_name_needed')
    return Intent('create_private_repo', args={'name': name},
                  requires_confirmation=True)


def _parse_google_search(t: str) -> Intent | None:
    """Perform only explicit Google searches, never guess an unclear phrase."""
    q = None
    # "busca iPhone en Google"; "búscame portátiles por internet"
    m = re.fullmatch(
        r'(?:busca(?:me)?|buscar|encuentra|investiga)\s+(.+?)'
        r'\s+(?:en|por)\s+(?:google|internet|la web)\s*', t)
    if m:
        q = m.group(1)
    else:
        # "busca en Google iPhone"; "buscar en internet protocolos USB"
        m = re.fullmatch(
            r'(?:busca(?:me)?|buscar|encuentra)\s+'
            r'(?:en|por)\s+(?:google|internet|la web)\s+(.+?)\s*', t)
        if m:
            q = m.group(1)
    if q is None:
        return None
    q = re.sub(r'^(?:informacion|datos)\s+sobre\s+', '', q).strip()
    if not 2 <= len(q) <= 180 or q in ('google', 'internet'):
        return Intent('search_query_needed')
    return Intent('google_search', args={'query': q})


def parse(text: str) -> Intent:
    spoken_command = extract_wake(text)
    t = spoken_command if spoken_command is not None else normalize(text)
    # Guard state-changing GitHub requests before generic web shortcuts.
    if re.fullmatch(r'(?:que puedes hacer|que sabes hacer|ayuda|comandos|mostrar comandos|lista de comandos)', t):
        return Intent('show_help')
    # The wake parser strips punctuation, including hyphens. For repo names,
    # keep the original spelling and join spoken name words explicitly.
    repo_request = _parse_private_repo_request(normalize(text))
    if repo_request is not None:
        return repo_request
    # Preserve punctuation inside search terms (for example "C++", "C#")
    # that the wake-word normalizer intentionally drops.
    search_text = re.sub(
        r'^(?:(?:oye|oie|oi|hey|hola|huji|uji|huyi)\s+)?'
        r'(?:hover|jover|over|llover|hober|huver|hoguer)\b[\s.,!?;:¿¡]*',
        '', normalize(text))
    search_request = _parse_google_search(search_text)
    if search_request is not None:
        return search_request
    # ASR inserts "Oye" even after the wake phrase: "Hover. Oye Calculadora".
    t = re.sub(r'^(?:oye|hey|eh|ok|vale)\s+(?=calculadora\b|calc\b|google\b|github\b|chatgpt\b|claude\b|spotify\b|abre\b)', '',t)
    # The simple assistant routes named apps and chat dictation before legacy tools.
    from .chat_command import parse_chat_request
    from .direct_commands import parse_direct
    req = parse_chat_request(text)
    if req is not None:
        return Intent(
            "chat_compose" if req.prompt else "chat_prepare",
            provider=req.provider,
            args={"project": req.project, "prompt": req.prompt},
        )
    direct = parse_direct(t)
    if direct is not None:
        return direct
    provider = identify_provider(t)
    # Whisper/Parakeet often returns just the app name after the wake word.
    # That is an explicit request to open it, not an unknown command.
    if t in ('chatgpt', 'chat gpt', 'chat gepete', 'chat e pepe'):
        return Intent('open_site','chatgpt')
    if t in ('claude','cloud','clout','clouding','clod','cloude','clau'):
        return Intent('open_site','claude')
    if t in ('spotify','espotifai','spotifai'):
        return Intent('spotify_play','spotify')
    if t in ('calculadora','la calculadora','calc'):
        return Intent('windows_app',args={'app':'calculator'})
    if t in ('github','git hub'):
        return Intent('open_link',args={'site':'github'})
    if t in ('google','el google'):
        return Intent('google_app',args={'service':'google_home'})
    if ('ultimo archivo' in t or 'ultimo fichero' in t) and 'descargas' in t and any(x in t for x in ('mueve', 'traslada', 'copia')):
        return Intent('move_latest_download' if 'mueve' in t or 'traslada' in t else 'copy_latest_download', requires_confirmation=True)
    if any(x in t for x in ('adjunta', 'adjuntalo', 'adjuntala', 'sube', 'carga archivo', 'envia el archivo')):
        match = re.search(r'(?:llamado|nombre|archivo|taller)\s+([\w .-]+?)(?:\s+(?:a|en|con|y|para)\s+|$)', t)
        name = match.group(1).strip() if match else ''
        prompt = ''
        m = re.search(r'(?:instrucciones|prompt|pidele|dile|que lo)\s*[: ]\s*(.+)$', t)
        if m: prompt = m.group(1)
        return Intent('upload_file', provider=provider, args={'filename':name, 'prompt':prompt}, requires_confirmation=True)
    if ('proyecto' in t) and provider in ('chatgpt','claude'):
        m=re.search(r'proyecto\s+(?:de\s+)?(?:chatgpt|chat gpt|claude|cloud)?\s*([\w.-]+)',t)
        return Intent('open_project',provider,{'name':m.group(1) if m else ''})
    if re.search(r'\b(cierra|cerrar)\b',t) and ('pestana' in t or 'chat' in t) and provider:
        return Intent('close_tab',provider,requires_confirmation=True)
    if any(x in t for x in ('preguntale','pregunta a','enviale','envia este prompt','escribe a','dile a')) and provider in ('chatgpt','claude'):
        m=re.search(r'(?:preguntale|pregunta a|enviale|envia este prompt|escribe a|dile a)\s+(?:a\s+)?(?:chatgpt|chat gpt|claude|cloud)?\s*(?:que|esto|lo siguiente|:)?\s*(.+)',t)
        prompt=(m.group(1) if m else '').strip(' :')
        if not prompt: return Intent('unknown')
        # Sending the explicitly dictated text to a chosen chat is a routine
        # action, not a purchase, deletion or file disclosure.
        # No typed "SI": the voice session must remain hands-free.
        if re.search(r'\b(preguntale|pregunta a)\b',t):
            from .chat_command import _question
            prompt=_question(prompt)
        return Intent('new_chat_and_send' if re.search(r'\b(nuevo chat|nueva conversacion|crea un chat|crear chat)\b',t) else 'send_prompt',provider,{'prompt':prompt})
    if re.search(r'\b(nuevo chat|nueva conversacion|crea un chat|crear chat)\b',t) and provider in ('chatgpt','claude'):
        return Intent('new_chat',provider)
    if re.search(r'(?:abre|abrir|accede|entra|ingresa|visita|muestra)\b',t) and provider in ('chatgpt','claude'):
        return Intent('open_site',provider)
    if provider=='spotify' and any(x in t for x in ('reproduce','reproces','pon','abre','inicia','reproducir')):
        return Intent('spotify_play',provider)
    if re.search(r'\b(muestrame|muestra|abre)\b.*\b(mi pc|este equipo|explorador|mi computador)\b',t):
        return Intent('show_pc')
    if re.search(r'\b(captura de pantalla|captura la pantalla|screenshot|recorte)\b',t):
        return Intent('screenshot')
    # Optional expert tools are explicit; no automatic Codex for everyday commands.
    if re.match(r'^(?:usa|con)\s+codex\b',t):
        task=re.sub(r'^(?:usa|con)\s+codex\s*','',t).strip()
        if not task: return Intent('unknown')
        if re.match(r'^(?:crea|crear|modifica|editar|edita|implementa|programa|desarrolla|corrige)\b',task):
            return Intent('agent_task',args={'prompt':task},requires_confirmation=True)
        return Intent('agent_ask',args={'prompt':task})
    return Intent('unknown')

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
    """Parse private GitHub repository names and trailing visibility phrases."""
    repository = r'(?:repo(?:sitorio)?s?|requisitori[oa]s?)'
    if not re.search(r'\b' + repository + r'\b', t):
        return None
    if not re.search(r'\bprivad[oa]s?\b', t):
        return None
    explicit = re.search(r'\b(?:crea|crear|creame|genera|generar)\b', t)
    uncertain = re.search(
        r'\bseria\s+uno\s+de\s+los\s+' + repository + r'\b', t)
    if not explicit and not uncertain:
        return None
    marker = re.search(
        r'\b(?:que\s+se\s+llam(?:a|e)|que\s+ya\s+me|que\s+llame|'
        r'llamad[oa]|con\s+el\s+nombre\s+de|nombre(?:\s+de)?)'
        r'\s*[,;:]?\s+(.+)$', t)
    if not marker:
        return Intent('repo_name_needed')
    raw_name = marker.group(1).strip(' \t.,;!?:')
    raw_name = re.sub(
        r'\s+(?:en\s+privad[oa]|de\s+forma\s+privad[oa]|'
        r'como\s+privad[oa]|privad[oa])$', '', raw_name).strip()
    words = raw_name.split()
    if not 1 <= len(words) <= 4:
        return Intent('repo_name_needed')
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]*',w) for w in words):
        return Intent('repo_name_needed')
    name='-'.join(words).strip('.-')
    if not 2 <= len(name) <= 80:
        return Intent('repo_name_needed')
    return Intent('create_private_repo',args={'name':name},requires_confirmation=True)


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
        m = re.fullmatch(
            r'(?:abre|abrir|muestra)\s+'
            r'(?:(?:(?:una|la|nueva)\s+)?'
            r'(?:pestana|presencia|pagina|ventana)\s+(?:de|en)\s+)?'
            r'google\s+y\s+(?:busca|buscar|buscame|encuentra)\s+(.+?)\s*',
            t,
        )
        if m:
            q = m.group(1)
    if q is None:
        return None
    q = re.sub(r'^(?:informacion|datos)\s+sobre\s+', '', q).strip()
    if not 2 <= len(q) <= 180 or q in ('google', 'internet'):
        return Intent('search_query_needed')
    return Intent('google_search', args={'query': q})


def _parse_local_creation(t: str) -> Intent | None:
    """Create a named TXT, subfolder or Excel only in HOVER's selected folder."""
    # Whisper sometimes hears "quería un archivo y texto" for
    # "crea un archivo de texto". Do not create anything from this
    # uncertain phrase; ask for the name of a TXT first.
    if re.fullmatch(
        r'queria\s+(?:(?:un|el)\s+)?archivo\s+(?:de|y)\s+texto', t
    ):
        return Intent("local_name_needed", args={"kind":"txt"})
    if not re.search(r'\b(?:crea|crear|creame|cree)\b', t):
        return None
    kind = None
    if re.search(r'\b(?:txt|archivo de texto|documento de texto)\b', t):
        kind = "txt"
    elif re.search(r'\b(?:subcarpeta|subcarpita|subcarbita|nueva carpeta)\b', t):
        kind = "folder"
    elif "excel" in t and re.search(r'\bcarpeta\b', t):
        kind = "excel"
    if not kind:
        return None
    marker = re.search(
        r'\b(?:que\s+se\s+llam(?:a|e)|que\s+llame|que\s+ya\s+me|'
        r'que\s+llega\s+a|llamad[oa]|de\s+nombre|con\s+nombre)'
        r'\s*[,;:]?\s+([a-z0-9][a-z0-9._ -]{0,90})\Z',t)
    if marker is None:
        return Intent("local_name_needed", args={"kind": kind})
    name = marker.group(1).strip(" .-")
    if not name or "/" in name or "\\" in name:
        return Intent("local_name_needed", args={"kind": kind})
    return Intent("create_local", args={"kind":kind, "name":name})


def parse(text: str) -> Intent:
    spoken_command = extract_wake(text)
    t = spoken_command if spoken_command is not None else normalize(text)
    # Guard state-changing GitHub requests before generic web shortcuts.
    if re.fullmatch(r'(?:que puedes hacer|que sabes hacer|ayuda|comandos|mostrar comandos|lista de comandos)', t):
        return Intent('show_help')
    # Google account searches/consent take precedence over public searches.
    # A private Google result is NEVER silently sent to ChatGPT or Claude.
    from .google_commands import parse_google_command
    goog = parse_google_command(t)
    if goog is not None:
        action,args,confirm=goog
        return Intent(action,args=args,requires_confirmation=confirm)
    # Recognize explicit and polite file-management imperatives BEFORE
    # information questions. Otherwise "puedes mover el último ZIP" is
    # incorrectly routed to a public Google search.
    # Fully scoped commands only: named user folders, bounded file types.
    from .pc_commands import parse_pc_command
    pc = parse_pc_command(t)
    if pc is not None:
        action, args = pc
        return Intent(action,args=args,requires_confirmation=False)
    # Natural information questions always go to Google before any app/file
    # routing: "como crear un repo" is research, NOT a repo creation command.
    # Explicit imperatives such as "crea un repositorio" do not match.
    from .information_queries import information_request, remove_wake_preserving_text
    # Keep accents and C++/C# intact for Google, even though the wake
    # detector normalizes punctuation for reliable activation.
    raw_info = remove_wake_preserving_text(text) if spoken_command is not None else text
    info = information_request(raw_info if raw_info is not None else t)
    if info is not None:
        return Intent(info[0], args=info[1])
    # The wake parser strips punctuation, including hyphens. For repo names,
    # keep the original spelling and join spoken name words explicitly.
    repo_request = _parse_private_repo_request(normalize(text))
    if repo_request is not None:
        return repo_request
    # "crea un tropo privado en GitHub" is an uncertain ASR rendition
    # of "crea un repo privado". It must NEVER auto-create a guessed slug.
    # Ask for the name explicitly; the next clearly dictated name can
    # complete the normal private-repo workflow.
    if (re.search(r'\b(?:crea|crear|creame)\b',t)
            and re.search(r'\btropo\s+privad[oa]\b',t)
            and re.search(r'\b(?:github|git hub)\b',t)):
        return Intent('repo_name_needed')
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
    local_request = _parse_local_creation(t)
    if local_request is not None:
        return local_request
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
    if re.fullmatch(
        r'(?:reproducelo|ponlo|dale play|reanuda spotify|'
        r'reanuda la musica|continua la musica|continua spotify)',t):
        return Intent('spotify_resume','spotify')
    if t in ('spotify','espotifai','spotifai'):
        return Intent('spotify_play','spotify')
    if t in ('calculadora','la calculadora','calc'):
        return Intent('windows_app',args={'app':'calculator'})
    if t in ('github','git hub'):
        return Intent('open_link',args={'site':'github'})
    if t in ('google','el google'):
        return Intent('google_app',args={'service':'google_home'})
    if ('ultimo archivo' in t or 'ultimo fichero' in t) and 'descargas' in t and any(x in t for x in ('mueve', 'traslada', 'copia')):
        return Intent('move_latest_download' if 'mueve' in t or 'traslada' in t else 'copy_latest_download')
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

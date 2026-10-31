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
    """Repo creation requires: explicit create verb, private intent, and name.

    The spoken syntax can freely order 'privado' and 'en GitHub'.
    Never create a public repository or guess a truncated name.
    """
    if not re.search(r'\b(?:crea|crear|creame|creame|genera|generar)\b',t):
        return None
    if not re.search(r'\b(?:repo|repositorio)\b',t):
        return None
    if not re.search(r'\bprivad[oa]\b',t):
        return None
    m = re.search(
        r'\b(?:que\s+se\s+llam(?:a|e)|llamad[oa]|con\s+el\s+nombre\s+de|nombre)\s+'
        r'([a-z0-9][a-z0-9._-]{1,99})(?=$|[\s,;!?])', t)
    if not m:
        return Intent('repo_name_needed')
    name = m.group(1).strip('.-')
    if not name or len(name)<2:
        return Intent('repo_name_needed')
    return Intent('create_private_repo',args={'name':name},requires_confirmation=True)


def parse(text: str) -> Intent:
    spoken_command = extract_wake(text)
    t = spoken_command if spoken_command is not None else normalize(text)
    # Guard state-changing GitHub requests before generic web shortcuts.
    if re.fullmatch(r'(?:que puedes hacer|que sabes hacer|ayuda|comandos|mostrar comandos|lista de comandos)', t):
        return Intent('show_help')
    repo_request = _parse_private_repo_request(t)
    if repo_request is not None:
        return repo_request
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
        return Intent('new_chat_and_send' if re.search(r'\b(nuevo chat|nueva conversacion|crea un chat|crear chat)\b',t) else 'send_prompt',provider,{'prompt':prompt},requires_confirmation=True)
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

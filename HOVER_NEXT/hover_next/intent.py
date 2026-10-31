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
    if re.search(r'\b(claude|cloud|clau)\b', t):
        return 'claude'
    if re.search(r'\b(spotify|spotifai|espotifai)\b', t):
        return 'spotify'
    return ''


def parse(text: str) -> Intent:
    spoken_command = extract_wake(text)
    t = spoken_command if spoken_command is not None else normalize(text)
    provider = identify_provider(t)
    if re.search(r'\b(crea|crear)\s+(?:un\s+)?(?:nuevo\s+)?repo(?:sitorio)?\s+(?:en\s+github\s+)?(?:privado\s+)?(?:llamado|que\s+se\s+llame)\s+([\w.-]+)', t):
        name = re.search(r'(?:llamado|que\s+se\s+llame)\s+([\w.-]+)', t).group(1)
        return Intent('create_private_repo', args={'name': name}, requires_confirmation=True)
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
    return Intent('unknown')

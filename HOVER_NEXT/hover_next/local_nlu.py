"""Offline Ollama semantic router for a bounded HOVER Windows/Google action set.

Only the local HTTP endpoint is contacted. Ollama never executes a tool: all
model output is untrusted, schema-checked, and grounded to the spoken request.
Direct legacy intents still work when Ollama is unavailable.
"""
from __future__ import annotations
from datetime import datetime
import json
import os
import re
import threading
import time
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import URLError

HOST="http://127.0.0.1:11434"
DEFAULT_MODEL="qwen2.5:3b"
FOLDERS={"desktop","downloads","documents","pictures","videos","music","favorite"}
APP_OPEN={"calculator","notepad","paint","explorer","vscode","terminal","task_manager","settings"}
APP_CLOSE=APP_OPEN|{"foreground","excel","word","powerpoint"}|FOLDERS
KINDS={"folder","text","excel","word","csv"}
FILE_TYPES={"any","archive","pdf","excel","image","text"}
ACTIONS={"unknown","pc_open_folder","pc_close_window","windows_app",
         "pc_create","pc_transfer","pc_rename","pc_append",
         "google_personal_search","google_create_event","gmail_create_draft"}
SCHEMA={
 "type":"object","additionalProperties":False,
 "properties":{
  "action":{"type":"string","enum":sorted(ACTIONS)},
  "location":{"type":"string"},"source":{"type":"string"},
  "destination":{"type":"string"},"app":{"type":"string"},
  "kind":{"type":"string"},"operation":{"type":"string"},
  "pick":{"type":"string"},"name":{"type":"string"},
  "new_name":{"type":"string"},"text":{"type":"string"},
  "query":{"type":"string"},"service":{"type":"string"},
  "title":{"type":"string"},"date_phrase":{"type":"string"},
  "time_phrase":{"type":"string"},
  "recipient":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}
 },
 "required":["action"]
}
PROMPT=(
 "Eres el intérprete de órdenes del asistente local HOVER en Windows, "
 "no un agente que ejecute herramientas. Devuelve SOLO JSON conforme al esquema. "
 "Comprende peticiones variadas en español y errores de Whisper. "
 "Las acciones permitidas son: "
 "pc_open_folder (location), pc_close_window (app), windows_app (app), "
 "pc_create (kind,name,location), pc_transfer (operation,pick,kind,source,destination,name), "
 "pc_rename (name,new_name,location), pc_append (name,text,location), "
 "google_personal_search (query,service), google_create_event "
 "(title,date_phrase,time_phrase), gmail_create_draft (recipient,subject,body). "
 "La ubicación de carpeta puede ser: desktop Escritorio, downloads Descargas "
 "(incluye 'las cargas'), documents Documentos, pictures Imágenes/Fotos, "
 "videos Vídeos, music Música, favorite carpeta favorita. "
 "App para cerrar puede ser una de esas carpetas o excel,word,powerpoint, "
 "explorer,calculator,paint,notepad,vscode,terminal,foreground. "
 "Apps para abrir: explorer,calculator,paint,notepad,vscode,terminal,settings,task_manager. "
 "Cualquier carpeta no especificada para CREAR por defecto desktop. "
 "Tipos creables: folder,text,excel,word,csv. "
 "Para buscar en correo usa google_personal_search service=gmail; calendario "
 "service=calendar; Drive service=drive; Google Docs service=docs. "
 "Para crear eventos sin hora, deja time_phrase vacío: será TODO EL DÍA, no inventes hora. "
 "Si el usuario no dijo un TÍTULO para el evento, usa title vacío; "
 "NUNCA pongas 'mañana', 'hoy', 'calendario', 'evento' o la fecha como título. "
 "Para borrador de Gmail, no inventes destinatario ni asunto. "
 "NO interpretes órdenes de eliminar/borrar, apagar, enviar email, instalar software, "
 "ejecutar programas/comandos desconocidos, modificar registro, buscar datos sensibles "
 "o acciones masivas: usa unknown. "
 "Nunca deduzcas archivos o datos faltantes. No interpretes preguntas "
 "(¿cómo puedo...?) como órdenes ejecutables. "
 "Los valores nombre/título/fecha/hora/destinatario/asunto/texto deben ser "
 "fragmentos fieles de las palabras del usuario, no inventados. "
 "No generes PowerShell ni rutas absolutas. "
 "Ejemplos:\n"
 "abre imágenes => {\"action\":\"pc_open_folder\",\"location\":\"pictures\"}\n"
 "cierra las cargas => {\"action\":\"pc_close_window\",\"app\":\"downloads\"}\n"
 "crea un evento mañana que diga reunión => "
 "{\"action\":\"google_create_event\",\"title\":\"reunión\",\"date_phrase\":\"mañana\"}\n"
 "búscame correos del proveedor => {\"action\":\"google_personal_search\","
 "\"service\":\"gmail\",\"query\":\"proveedor\"}\n"
 "crea un borrador de correo asunto informe texto terminado => "
 "{\"action\":\"gmail_create_draft\",\"subject\":\"informe\",\"body\":\"terminado\"}\n"
 "cómo abro imágenes => {\"action\":\"unknown\"}\n"
)
_CACHE_LOCK=threading.Lock()
_CACHE={}
_MISSING_UNTIL=0.0


def clean(value):
    normalized="".join(c for c in unicodedata.normalize("NFKD",str(value).casefold())
                       if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",normalized).strip(" \t.,!?¿¡")


def anchored(value,spoken):
    word=clean(value)
    return bool(1<=len(word)<=180 and word in clean(spoken))


def _candidate(spoken):
    """A known action verb is required; the model cannot invent an action."""
    t=clean(spoken)
    if len(t)<5 or len(t)>320:
        return False
    if re.match(r"^(?:como|por que|que significa|explicame|me explicas)\b",t):
        return False
    if re.search(r"\b(?:elimina|eliminar|borra|borrar|apaga|apagar|"
                 r"shutdown|reinstala|instala|desinstala|ejecuta scripts|"
                 r"powershell|cmd /|envia|enviar|manda un correo)\b",t):
        return False
    return bool(re.search(
        r"\b(?:abre|abrir|abreme|abran|muestra|muestrame|"
        r"cierra|cerrar|cierrame|sierra|"
        r"crea|crear|creame|hazme|prepara|programa|agenda|anota|"
        r"busca|buscame|revisa|encuentra|consulta|"
        r"copia|copiar|mueve|mover|pasa|pasame|traslada|"
        r"renombra|cambiale|agrega|escribe|redacta)\b",t))


def validate(output,spoken):
    """Pure deterministic validation independent of any LLM prompt."""
    if not isinstance(output,dict) or set(output)-set(SCHEMA["properties"]):
        return None
    if any(not isinstance(v,str) for v in output.values()):
        return None
    action=output.get("action")
    if action not in ACTIONS or action=="unknown":
        return None
    from .intent import Intent
    if action=="pc_open_folder":
        loc=output.get("location")
        return Intent(action,args={"location":loc}) if loc in FOLDERS else None
    if action=="pc_close_window":
        app=output.get("app") or output.get("location")
        return Intent(action,args={"app":app}) if app in APP_CLOSE else None
    if action=="windows_app":
        app=output.get("app")
        return Intent(action,args={"app":app}) if app in APP_OPEN else None
    if action=="pc_create":
        kind=output.get("kind")
        name=output.get("name","")
        location=output.get("location") or "desktop"
        if kind not in KINDS or location not in FOLDERS or not anchored(name,spoken):
            return None
        return Intent(action,args={"kind":kind,"name":name,"location":location})
    if action=="pc_transfer":
        op=output.get("operation")
        src,dst=output.get("source"),output.get("destination")
        pick=output.get("pick")
        if op not in ("move","copy") or src not in FOLDERS or dst not in FOLDERS or src==dst:
            return None
        args={"operation":op,"from":src,"to":dst}
        if pick=="latest" and output.get("kind") in FILE_TYPES:
            args.update({"pick":"latest","kind":output["kind"]})
        elif pick=="name" and anchored(output.get("name",""),spoken):
            args.update({"pick":"name","name":output["name"]})
        else:
            return None
        return Intent(action,args=args)
    if action=="pc_rename":
        src,nxt=output.get("name",""),output.get("new_name","")
        loc=output.get("location")
        if loc not in FOLDERS or not anchored(src,spoken) or not anchored(nxt,spoken):
            return None
        return Intent(action,args={"location":loc,"old":src,"new":nxt})
    if action=="pc_append":
        filename,body=output.get("name",""),output.get("text","")
        loc=output.get("location")
        if loc not in FOLDERS or not anchored(filename,spoken) or not anchored(body,spoken):
            return None
        if len(body)>500:
            return None
        return Intent(action,args={"location":loc,"name":filename,"text":body})
    if action=="google_personal_search":
        term,svc=output.get("query",""),output.get("service","")
        if svc not in ("gmail","drive","calendar","docs") or not anchored(term,spoken):
            return None
        return Intent(action,args={"query":term,"source":svc})
    if action=="google_create_event":
        title,date=output.get("title",""),output.get("date_phrase","")
        hour=output.get("time_phrase","")
        if not anchored(date,spoken) or len(date)>100:
            return None
        if hour and not anchored(hour,spoken):
            return None
        # A source-grounded title must be independent of the date. The
        # actual Windows transcript was "crea un evento ... para mañana"
        # and Qwen wrongly set title="manana". Never create that event.
        generic={"evento","calendario","calendar","cita","recordatorio",
                 "hoy","manana","pasado manana","proximo dia"}
        clean_title=clean(title)
        clean_date=clean(date)
        missing=(not title or clean_title in generic or
                 clean_title==clean_date or
                 not anchored(title,spoken) or len(title)>120)
        if missing:
            if "evento" not in clean(spoken) and "calendario" not in clean(spoken):
                return None
            return Intent("google_event_title_needed",
                          args={"date_phrase":date,"time_phrase":hour})
        return Intent(action,args={
            "title":title,"date_phrase":date,"time_phrase":hour})
    if action=="gmail_create_draft":
        recipient=output.get("recipient","")
        subject=output.get("subject","")
        body=output.get("body","")
        if not anchored(subject,spoken) or len(subject)>150 or len(body)>2000:
            return None
        if body and not anchored(body,spoken):
            return None
        if recipient and (not anchored(recipient,spoken) or not re.fullmatch(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",recipient)):
            return None
        return Intent(action,args={"recipient":recipient,"subject":subject,"body":body})
    return None


def model_intent(spoken):
    global _MISSING_UNTIL
    if not _candidate(spoken) or os.environ.get("HOVER_NLU","auto").lower()=="off":
        return None
    now=time.monotonic()
    with _CACHE_LOCK:
        cached=_CACHE.get(spoken)
        if cached is not None and now-cached[0]<8:
            return cached[1]
        if now<_MISSING_UNTIL:
            return None
    model=os.environ.get("HOVER_NLU_MODEL",DEFAULT_MODEL)
    if not re.fullmatch(r"[A-Za-z0-9][\w.:-]{1,80}",model):
        return None
    request=json.dumps({
        "model":model,"stream":False,
        "messages":[{"role":"system","content":PROMPT},
                    {"role":"user","content":spoken}],
        "format":SCHEMA,"options":{"temperature":0,"num_predict":256},
        "keep_alive":"10m"
    },ensure_ascii=False).encode("utf-8")
    try:
        req=Request(HOST+"/api/chat",data=request,headers={
            "Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=7) as response:
            raw=response.read(24000)
        wrapper=json.loads(raw)
        msg=wrapper.get("message",{})
        decoded=json.loads(msg.get("content",""))
        answer=validate(decoded,spoken)
    except (URLError,OSError,ValueError,KeyError,TypeError,TimeoutError):
        # Brief circuit-breaker when Ollama is absent; voice keeps working.
        with _CACHE_LOCK:
            _MISSING_UNTIL=time.monotonic()+12
        return None
    with _CACHE_LOCK:
        if len(_CACHE)>32:
            _CACHE.clear()
        _CACHE[spoken]=(time.monotonic(),answer)
    return answer

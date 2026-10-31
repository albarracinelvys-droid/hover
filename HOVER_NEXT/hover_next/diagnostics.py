"""Read-only HOVER voice diagnostics. Never access OAuth tokens or send audio.

Checks the saved HOVER voice log, current process, and offline parser without
executing any Windows action or accessing a connected account.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.request import urlopen
import json
import os
import re
import statistics

from .launch_background import state_paths, _running_hover_process


def recent_log(limit_bytes=120_000):
    _,path=state_paths()
    try:
        with path.open("rb") as file:
            file.seek(0,2)
            size=file.tell()
            file.seek(max(0,size-limit_bytes))
            content=file.read().decode("utf-8",errors="replace")
    except OSError:
        return ""
    # Only the current/most recent process; do not mix older runs.
    marker="[launcher] Iniciando HOVER"
    if marker in content:
        content=content.rsplit(marker,1)[-1]
    return content


def summarize(content):
    summary=Counter()
    for line in content.splitlines():
        if line.startswith("[ready] HOVER"):
            summary["ready"]+=1
        if line.startswith("[voz]"):
            summary["voice"]+=1
        if line.startswith("[accion]"):
            summary["intent"]+=1
        if "[accion] Sin coincidencia:" in line:
            summary["unknown"]+=1
        if "[asr] No hubo palabras claras" in line:
            summary["no_words"]+=1
        if "[asr] Fragmento descartado por ruido" in line:
            summary["noise"]+=1
        if "[idle] No se reconocio el nombre Hover" in line:
            summary["no_wake"]+=1
        if "HOVER - error controlado:" in line or "[asr] Error:" in line:
            summary["execution_errors"]+=1
        if line.startswith("HOVER:"):
            summary["executed"]+=1
        if line.startswith("[mic] RMS=") and "voz=si" in line:
            summary["voice_active"]+=1
        if line.startswith("[latencia] cola="):
            for name,raw in re.findall(
                    r"\b(cola|asr|interpretacion_y_accion|total)=(\d+(?:\.\d+)?)ms",
                    line):
                summary.setdefault("_"+name,[]).append(float(raw))
    return summary


def ollama_status():
    """GET /api/tags only; never asks the LLM to classify or execute."""
    from .local_nlu import DEFAULT_MODEL
    if os.environ.get("HOVER_NLU","auto").lower()=="off":
        return "DESACTIVADO por HOVER_NLU=off"
    model=os.environ.get("HOVER_NLU_MODEL",DEFAULT_MODEL)
    try:
        with urlopen("http://127.0.0.1:11434/api/tags",timeout=1.5) as response:
            body=json.loads(response.read(100_000))
        models=body.get("models",[])
        if not isinstance(models,list):
            return "Respuesta inesperada de Ollama"
        available={str(x.get("name","")) for x in models if isinstance(x,dict)}
        if model in available or model+":latest" in available:
            return f"ACTIVO · modelo {model} instalado"
        return f"ACTIVO · falta descargar {model} (ollama pull {model})"
    except (OSError,ValueError,TypeError):
        return "NO RESPONDE · inicia Ollama en Windows"


def latest_unknowns(content,limit=3):
    """Only unknown voice commands; don't publish a full private log."""
    values=[]
    prefix="[accion] Sin coincidencia:"
    for line in content.splitlines():
        if line.startswith(prefix):
            values.append(line[len(prefix):].strip()[:150])
    return values[-limit:]


def quick_check():
    from .intent import parse
    pid=_running_hover_process()
    print("HOVER - Diagnóstico local (no modifica tu PC ni Google)")
    print("Motor de voz:",f"ACTIVO (PID {pid})" if pid else "NO DETECTADO")
    _,path=state_paths()
    print("Registro:",path)
    print("Modelo local Ollama:",ollama_status())
    content=recent_log()
    if not content:
        print("No hay registros recientes. Inicia HOVER y prueba una orden.")
    else:
        stats=summarize(content)
        for key,label in (
            ("ready","Inicios listos"),
            ("voice","Frases reconocidas"),
            ("intent","Acciones interpretadas"),
            ("unknown","Órdenes desconocidas"),
            ("no_words","Audios sin palabras claras"),
            ("no_wake","Frases sin activación Hover"),
            ("execution_errors","Errores ejecutando acciones"),
        ):
            print(f"{label}: {stats[key]}")
        for key,label in (("asr","Whisper/Parakeet"),
                          ("interpretacion_y_accion","Interpretación y ejecución"),
                          ("total","Tiempo tras fin del dictado")):
            values=stats.get("_"+key,[])
            if values:
                print(f"{label} (mediana): {statistics.median(values):.0f}ms")
        if stats["no_words"] or stats["no_wake"]:
            print("Sugerencia: verifica el micrófono y la transcripción; "
                  "puedes probar con F8.")
        if stats["unknown"]:
            print("Sugerencia: el texto llegó, pero no se identificó una acción.")
            print("Últimas órdenes no reconocidas (revisa datos privados antes de compartir):")
            for utterance in latest_unknowns(content):
                print("  -",utterance)
            reasons=[line.strip() for line in content.splitlines()
                     if line.startswith("[nlu]")]
            if reasons:
                print("Últimas decisiones del intérprete local:")
                for message in reasons[-5:]:
                    print("  ",message)
            else:
                print("  No hay detalles NLU en este registro; usa la versión actualizada.")
        if stats["execution_errors"]:
            print("Sugerencia: algunas órdenes se entendieron pero fallaron "
                  "al ejecutarse. Consulta voice.log para ver el motivo.")

    # Offline parser smoke-check: no actual programs, Spotify, or files opened.
    print("Comprobación segura del intérprete:")
    for spoken in ("abre calculadora","reproduce Spotify",
                   "cierra el explorador de archivos","Hover bye bye"):
        try:
            action=parse(spoken).action
        except Exception as exc:
            action="ERROR:"+type(exc).__name__
        print(f"  {spoken!r} -> {action}")
    print("No se ejecutaron acciones; no se cambiaron archivos ni permisos.")
    return 0


if __name__=="__main__":
    raise SystemExit(quick_check())

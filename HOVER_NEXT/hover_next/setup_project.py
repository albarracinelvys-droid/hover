"""Local, one-time setup for ChatGPT or Claude project names.

Only trusted HTTPS project URLs are accepted. No passwords are stored.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from .executor import app_dir

HOSTS = {"chatgpt": {"chatgpt.com", "chat.openai.com"},
         "claude": {"claude.ai"}}

def save_project(config_file: Path, provider: str, name: str, url: str):
    provider = provider.lower().strip()
    name = name.casefold().strip()
    if provider not in HOSTS:
        raise ValueError("El proveedor debe ser ChatGPT o Claude.")
    if not name or len(name) > 61:
        raise ValueError("Nombre de proyecto inválido.")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in HOSTS[provider] or not parsed.path.strip("/"):
        raise ValueError("Pega la URL HTTPS completa de un proyecto de ChatGPT o Claude.")
    if provider == "chatgpt" and "/g/g-p-" not in parsed.path:
        raise ValueError("Pega la URL de la página del proyecto Zap, no la URL de un chat individual.")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_file.read_text("utf-8")) if config_file.exists() else {}
    config.setdefault("projects", {}).setdefault(provider, {})[name] = url.strip()
    tmp = config_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(config_file)
    return config_file

def main():
    provider = (sys.argv[1] if len(sys.argv) > 1 else "chatgpt").casefold()
    name = (sys.argv[2] if len(sys.argv) > 2 else "zap").casefold()
    print(f"Configurar proyecto {name} en {provider}")
    print("Abre ese proyecto en tu navegador y copia su URL real.")
    url = input("Pega la URL del proyecto y pulsa Enter: ").strip()
    if not url:
        print("Sin cambios.")
        return
    try:
        location = save_project(app_dir()/"config.json", provider, name, url)
        print(f"Proyecto configurado en {location}; no se almaceno ninguna contraseña.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("No pude guardar el proyecto:",exc)
        raise SystemExit(1)

if __name__=="__main__":
    main()

"""Shared project links managed by HOVER's Windhawk shortcuts interface.

The native UI owns %LOCALAPPDATA%/HOVER_NEXT/projects.tsv; this module reads
the same file. An existing config.json stays intact and is used as fallback.
"""
from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import urlparse

VALID_HOSTS = {
    "chatgpt": {"chatgpt.com"},
    "claude": {"claude.ai"},
}

def project_store() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HOVER_NEXT" / "projects.tsv"

def valid_project_url(provider: str, url: str) -> bool:
    parsed = urlparse(url.strip())
    if provider not in VALID_HOSTS or parsed.scheme != "https":
        return False
    if parsed.hostname not in VALID_HOSTS[provider] or parsed.username or parsed.password:
        return False
    if provider == "chatgpt":
        return parsed.path.startswith("/g/g-p-")
    return parsed.path.startswith("/project/")

def read_project_links(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = path or project_store()
    projects: dict[str, dict[str, str]] = {"chatgpt": {}, "claude": {}}
    if not p.is_file():
        return projects
    if p.stat().st_size > 32768:
        raise ValueError("projects.tsv demasiado grande.")
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        provider, name, url = parts
        provider = provider.strip().casefold()
        name = name.strip().casefold()
        url = url.strip()
        if name and len(name) < 64 and valid_project_url(provider, url):
            projects[provider][name] = url
    return projects

def get_project_url(config: dict, provider: str, name: str) -> str:
    provider = provider.casefold()
    name = name.casefold()
    # Native shortcut editor takes priority over legacy JSON configuration.
    local = read_project_links().get(provider, {}).get(name)
    if local:
        return local
    legacy = config.get("projects", {}).get(provider, {}).get(name, "")
    return legacy if valid_project_url(provider, legacy) else ""

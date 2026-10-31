"""Open a successfully created PRIVATE GitHub repository in Chrome.

Do not guess a URL from a misheard name. Accept a verified GitHub URL from
GitHub CLI and confirm its final path segment equals the created repo name.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import shutil
import subprocess
import webbrowser
from urllib.parse import urlparse


def created_repo_url(output: str, name: str) -> str:
    for match in re.finditer(
        r'https://github[.]com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+', output
    ):
        candidate = match.group(0).rstrip(".")
        parsed = urlparse(candidate)
        segments = parsed.path.strip("/").split("/")
        if (parsed.scheme == "https" and parsed.hostname == "github.com"
                and len(segments) == 2
                and segments[1].casefold() == name.casefold()):
            return candidate
    return ""


def _chrome_paths():
    exe = shutil.which("chrome.exe") or shutil.which("chrome")
    if exe:
        yield Path(exe)
    for root, tail in (
        ("PROGRAMFILES", r"Google\Chrome\Application\chrome.exe"),
        ("PROGRAMFILES(X86)", r"Google\Chrome\Application\chrome.exe"),
        ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
    ):
        parent = os.environ.get(root)
        if parent:
            yield Path(parent) / tail


def show_repo(url: str) -> str:
    parsed=urlparse(url)
    if (parsed.scheme!="https" or parsed.netloc!="github.com"
            or len(parsed.path.strip("/").split("/"))!=2):
        raise ValueError("GitHub devolvió una dirección inesperada.")
    for chrome in _chrome_paths():
        if chrome.is_file():
            try:
                subprocess.Popen([str(chrome), url], shell=False)
                return "Google Chrome"
            except OSError:
                continue
    # The default browser is a safe fallback on systems without Chrome.
    if webbrowser.open_new_tab(url):
        return "navegador predeterminado"
    return ""

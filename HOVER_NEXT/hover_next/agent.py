"""Optional local CLI brains for HOVER, inspired by Coucou's provider approach.

No key or subscription is copied into HOVER. Sign in with your official CLI.
Read-only questions never edit files. Coding tasks need explicit confirmation
and a preconfigured trusted workspace. Never uses full-access or bypass flags.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

class AgentUnavailable(RuntimeError):
    pass

def _workspace(config: dict, write: bool) -> Path:
    configured = config.get("agent_workspace", "")
    if write and not configured:
        raise AgentUnavailable("Configura agent_workspace en config.json para permitir ediciones.")
    root = Path(configured).expanduser() if configured else Path.home()
    if not root.is_dir():
        raise AgentUnavailable(f"No existe la carpeta configurada: {root}")
    return root.resolve()

def run_agent(prompt: str, config: dict, *, write: bool = False, timeout: int = 240) -> str:
    provider = str(config.get("agent_provider", "codex")).lower().strip()
    if provider not in ("codex", "claude"):
        raise AgentUnavailable("agent_provider debe ser codex o claude.")
    prompt = prompt.strip()
    if not prompt or len(prompt) > 10000:
        raise ValueError("La instruccion debe contener entre 1 y 10000 caracteres.")
    cwd = _workspace(config, write)
    executable = shutil.which(provider)
    if not executable:
        raise AgentUnavailable(
            f"No se encontro {provider} en PATH. Instala la CLI oficial e inicia sesion."
        )
    if provider == "codex":
        args = [executable, "exec", "--sandbox", "workspace-write" if write else "read-only",
                "--skip-git-repo-check", "--cd", str(cwd), "-"]
    elif write:
        raise AgentUnavailable("Por seguridad, HOVER solo permite ediciones con Codex sandbox workspace-write.")
    else:
        args = [executable, "-p", "--permission-mode", "plan", prompt]

    try:
        proc = subprocess.run(
            args,
            input=prompt if provider == "codex" else None,
            text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(cwd), timeout=timeout, shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentUnavailable("El agente excedio el tiempo limite.") from exc
    if proc.returncode:
        err = (proc.stderr or proc.stdout or "").strip()
        raise AgentUnavailable(f"{provider} termino con error: {err[-500:]}")
    result = (proc.stdout or "").strip()
    if not result:
        raise AgentUnavailable(f"{provider} termino sin entregar un resultado.")
    return result[:12000]

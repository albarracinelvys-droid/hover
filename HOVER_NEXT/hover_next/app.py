"""HOVER NEXT: silent CLI, visual bridge and microphone diagnostics."""
from __future__ import annotations

import argparse
from .intent import Intent, parse
from .executor import Executor, confirm_intent, confirm_voice_intent
from .ui_bridge import publish, status_page


def voice_may_autocreate_private_repo(command, intent) -> bool:
    """Allow a clear voice command to create a private repo without a dialog.

    The user explicitly opted into this workflow. Transcripts with tentative
    wording or unclear/missing names still require visual confirmation.
    This exception applies ONLY to private repository creation, never other
    file modifications, payments or deletions.
    """
    if intent.action != "create_private_repo":
        return False
    from .intent import normalize
    import re
    from .wake import extract_wake
    # VoiceDialogue strips the wake phrase BEFORE calling run_one;
    # direct tests may still supply the full utterance.
    spoken = extract_wake(command)
    t = normalize(spoken if spoken is not None else command)
    if not re.search(r'\b(?:crea|crear|creame|genera)\b', t):
        return False
    if not re.search(r'\b(?:repositorio|repo)\b', t):
        return False
    if not re.search(r'\bprivad[oa]\b', t):
        return False
    if not re.search(r'\b(?:que se llam[ae]|llamad[oa]|con el nombre de)\b',t):
        return False
    name = intent.args.get("name","")
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,79}",name))


def run_one(command, executor, *, voice_mode=False):
    intent = parse(command)
    print("Interpretado:", intent, flush=True)
    if intent.action == "unknown":
        publish("error", "No pude interpretar esa instruccion")
        print("HOVER: No pude interpretar esa instruccion.", flush=True)
        return None
    if (intent.action == "pc_delete" or
            (intent.action == "pc_transfer" and
             intent.args.get("pick") == "latest")):
        # Freeze the exact file before immediate execution, preserving
        # stale-file protection without a separate confirmation dialog.
        try:
            from .pc_files import prepare_transfer, prepare_delete
            args=(prepare_delete(intent.args,executor.config)
                  if intent.action=="pc_delete"
                  else prepare_transfer(intent.args,executor.config))
            intent=Intent(intent.action,intent.provider,args,intent.requires_confirmation)
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
            publish("error",error)
            print("HOVER - error controlado:",error,flush=True)
            return None
    auto_repo = voice_mode and voice_may_autocreate_private_repo(command,intent)
    if intent.requires_confirmation and not auto_repo:
        publish("thinking", "Confirmar antes de ejecutar: " + intent.action, status_page(intent.action))
        if not (confirm_voice_intent(intent) if voice_mode else confirm_intent(intent)):
            publish("ok", "Operacion cancelada")
            print("Cancelado; no se realizo ninguna accion.", flush=True)
            return None
    if auto_repo:
        print("[github] Creacion privada autorizada por la orden de voz explicita: "
              +intent.args["name"],flush=True)
        publish("thinking", "Creando repo privado: "+intent.args["name"], 3)
    try:
        publish("thinking", "Ejecutando: " + intent.action, status_page(intent.action))
        result = executor.execute(intent, confirmed=True)
        print("HOVER:", result, flush=True)
        publish("ok", str(result), status_page(intent.action))
        return result
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print("HOVER - error controlado:", error, flush=True)
        publish("error", error)
        return None


def main():
    parser = argparse.ArgumentParser(description="HOVER - agente de escritorio sin voz sintetizada")
    parser.add_argument("--text", help="Ejecutar una frase escrita")
    parser.add_argument("--voice", action="store_true", help="Escuchar con Whisper local")
    parser.add_argument("--mic-test", action="store_true", help="Medir sonido del microfono sin Whisper")
    parser.add_argument("--mic", type=int, default=None, help="Indice del microfono")
    parser.add_argument("--threshold", type=float, default=0.0008, help="Umbral RMS, predeterminado 0.0008")
    parser.add_argument("--model", default="small", help="Modelo faster-whisper si no hay Parakeet")
    parser.add_argument("--engine", choices=("auto","parakeet","whisper"),default="auto",
                        help="Auto elige Parakeet si esta instalado; si no Whisper")
    parser.add_argument("--install-parakeet",action="store_true",
                        help="Descargar y verificar el modelo local usado por Coucou")
    args = parser.parse_args()
    if args.install_parakeet:
        from .recognizers import install_parakeet
        install_parakeet()
        return
    if args.mic_test:
        from .voice import test_microphone
        test_microphone(device=args.mic,threshold=args.threshold)
        return
    executor = Executor()
    if args.voice:
        from .single_instance import AlreadyRunning, voice_instance
        from .voice_coucou import run
        preferred=executor.config.get("preferred_mic") if args.mic is None else args.mic
        mic=int(preferred) if preferred is not None else None
        try:
            with voice_instance():
                publish("idle", "HOVER listo: silencioso")
                try:
                    run(executor,engine=args.engine,model=args.model,
                        device=mic,threshold=args.threshold)
                finally:
                    publish("idle", "")
        except AlreadyRunning as exc:
            print("[HOVER]",exc,flush=True)
        return
    publish("idle", "HOVER listo: silencioso")
    try:
        if args.text:
            run_one(args.text,executor)
        else:
            print("HOVER listo. Escribe un comando o salir.")
            while True:
                try:
                    command=input("> ").strip()
                except (KeyboardInterrupt,EOFError):
                    break
                if command.casefold() in ("salir","exit"):
                    break
                if command:
                    run_one(command,executor)
    finally:
        publish("idle","")
        executor.browser.close()


if __name__ == "__main__":
    main()

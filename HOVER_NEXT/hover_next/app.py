"""HOVER NEXT: silent CLI, visual bridge and microphone diagnostics."""
from __future__ import annotations

import argparse
from .intent import parse
from .executor import Executor, confirm_intent
from .ui_bridge import publish, status_page


def run_one(command, executor):
    intent = parse(command)
    print("Interpretado:", intent, flush=True)
    if intent.action == "unknown":
        publish("error", "No pude interpretar esa instruccion")
        print("HOVER: No pude interpretar esa instruccion.", flush=True)
        return None
    if intent.requires_confirmation:
        publish("thinking", "Confirmar antes de ejecutar: " + intent.action, status_page(intent.action))
        if not confirm_intent(intent):
            publish("ok", "Operacion cancelada")
            print("Cancelado; no se realizo ninguna accion.", flush=True)
            return None
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
    parser.add_argument("--model", default="small", help="Modelo faster-whisper")
    args = parser.parse_args()
    if args.mic_test:
        from .voice import test_microphone
        test_microphone(device=args.mic,threshold=args.threshold)
        return
    executor = Executor()
    publish("idle", "HOVER listo: silencioso")
    try:
        if args.voice:
            from .voice import run_voice
            run_voice(executor,args.model,device=args.mic,threshold=args.threshold)
        elif args.text:
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
        publish("idle", "")
        executor.browser.close()


if __name__ == "__main__":
    main()

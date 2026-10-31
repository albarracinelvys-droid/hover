"""HOVER NEXT - command line, microphone diagnostic, and local voice."""
from __future__ import annotations
import argparse
from .intent import parse
from .executor import Executor, confirm_intent


def run_one(command, executor):
    intent = parse(command)
    print("Interpretado:", intent, flush=True)
    if not confirm_intent(intent):
        print("Cancelado; no se realizó ninguna acción.", flush=True)
        return
    try:
        print("HOVER:", executor.execute(intent, confirmed=True), flush=True)
    except Exception as exc:
        print(f"Error controlado: {exc}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="HOVER NEXT - asistente modular")
    parser.add_argument("--text", help="Ejecutar una frase escrita")
    parser.add_argument("--voice", action="store_true", help="Escucha con Whisper local")
    parser.add_argument("--mic-test", action="store_true",
                        help="Muestra el nivel del micrófono, sin cargar Whisper")
    parser.add_argument("--mic", type=int, default=None,
                        help="Número del micrófono según sounddevice.query_devices()")
    parser.add_argument("--threshold", type=float, default=0.0008,
                        help="Umbral RMS: 0.0008 predeterminado; bájalo si no detecta voz")
    parser.add_argument("--model", default="small")
    args = parser.parse_args()

    if args.mic_test:
        from .voice import test_microphone
        test_microphone(device=args.mic, threshold=args.threshold)
        return

    executor = Executor()
    try:
        if args.voice:
            from .voice import run_voice
            run_voice(executor, args.model, device=args.mic,
                      threshold=args.threshold)
        elif args.text:
            run_one(args.text, executor)
        else:
            print("HOVER listo. Escribe un comando o salir.")
            while True:
                try:
                    command = input("> ").strip()
                except (KeyboardInterrupt, EOFError):
                    break
                if command.casefold() in ("salir", "exit"):
                    break
                if command:
                    run_one(command, executor)
    finally:
        executor.browser.close()


if __name__ == "__main__":
    main()

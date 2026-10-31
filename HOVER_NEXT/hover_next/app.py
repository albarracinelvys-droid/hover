"""Command-line controller. Test commands without microphone first."""
from __future__ import annotations
import argparse
from .intent import parse
from .executor import Executor,confirm_intent

def run_one(command, executor):
    intent=parse(command)
    print('Interpretado:',intent)
    if not confirm_intent(intent):
        print('Cancelado; no se realizo ninguna accion.')
        return
    try:print('HOVER:',executor.execute(intent,confirmed=True))
    except Exception as exc:print(f'Error controlado: {exc}')

def main():
    parser=argparse.ArgumentParser(description='HOVER NEXT - asistente modular')
    parser.add_argument('--text',help='Ejecutar una frase escrita')
    parser.add_argument('--voice',action='store_true',help='Escucha con Whisper local')
    parser.add_argument('--model',default='small')
    args=parser.parse_args()
    executor=Executor()
    if args.voice:
        from .voice import run_voice
        run_voice(executor,args.model)
    elif args.text:run_one(args.text,executor)
    else:
        print('HOVER listo. Escribe un comando o salir.')
        while True:
            try:command=input('> ').strip()
            except (KeyboardInterrupt,EOFError):break
            if command.casefold() in ('salir','exit'):break
            if command:run_one(command,executor)
    executor.browser.close()

if __name__=='__main__':main()

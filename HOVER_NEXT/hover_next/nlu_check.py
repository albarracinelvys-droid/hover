"""Smoke-check the local language model without executing Windows/Google actions."""
from __future__ import annotations
import sys
from .local_nlu import model_intent

def main():
    samples=[
        ("abre imágenes","pc_open_folder"),
        ("cierra las cargas","pc_close_window"),
        ("crea un evento para mañana que diga reunión","google_create_event"),
    ]
    success=0
    for text,expected in samples:
        got=model_intent(text)
        actual=got.action if got else "SIN_MODELO"
        print(f"[modelo] {text!r} -> {actual}",flush=True)
        success+=int(actual==expected)
    print(f"[modelo] {success}/{len(samples)} casos interpretados correctamente.")
    if not success:
        print("Comprueba que Ollama y qwen2.5:3b estén disponibles localmente.")
    return 0 if success==len(samples) else 2

if __name__=="__main__":
    sys.exit(main())

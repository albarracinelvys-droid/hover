"""Read-only diagnostics and full spoken-intent routing regressions."""
from __future__ import annotations
from collections import Counter
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from hover_next import diagnostics
from hover_next.intent import Intent
from hover_next.voice_coucou import VoiceDialogue
from hover_next.audio_coucou import AdaptiveVad, FRAME
import numpy as np


class DiagnosticsTests(unittest.TestCase):
    def test_classifies_actual_failure_stage_without_executing_commands(self):
        log=(
            "[ready] HOVER v5 | Whisper Small\n"
            "[mic] RMS=0.001 umbral=0.0008 voz=si cola=0\n"
            "[voz] Hover, abre calculadora.\n"
            "[accion] windows_app {'app':'calculator'}\n"
            "HOVER: Calculadora abierta.\n"
            "[latencia] cola=5ms asr=510ms "
            "interpretacion_y_accion=120ms total=635ms\n"
            "[voz] Hover, abre imágenes.\n"
            "[accion] Sin coincidencia: abre imágenes\n"
            "[asr] No hubo palabras claras. Intenta hablar mas cerca.\n"
            "[idle] No se reconocio el nombre Hover. Prueba F8.\n"
            "HOVER - error controlado: PCFileError: No disponible\n"
        )
        data=diagnostics.summarize(log)
        self.assertEqual(data["ready"],1)
        self.assertEqual(data["voice"],2)
        self.assertEqual(data["unknown"],1)
        self.assertEqual(data["execution_errors"],1)
        self.assertEqual(data["_asr"],[510])
        self.assertEqual(data["_total"],[635])
        self.assertEqual(data["no_wake"],1)

    def test_diagnostics_reads_only_latest_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"voice.log"
            path.write_text(
                "[launcher] Iniciando HOVER v5 sin terminal.\n"
                "[accion] Sin coincidencia: comando antiguo\n"
                "[launcher] Iniciando HOVER v5 sin terminal.\n"
                "[voz] Hover, abre calculadora\n",encoding="utf-8")
            with patch("hover_next.diagnostics.state_paths",
                       return_value=(Path(tmp)/"voice.pid",path)):
                latest=diagnostics.recent_log()
        self.assertNotIn("comando antiguo",latest)
        self.assertIn("[voz] Hover, abre calculadora",latest)

    def test_safe_diagnostic_never_executes_apps_or_creates_calendar_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"voice.log"
            path.write_text("[ready] HOVER v5 | Whisper Small\n",encoding="utf-8")
            output=io.StringIO()
            with patch("hover_next.diagnostics._running_hover_process",
                       return_value=1234), \
                 patch("hover_next.diagnostics.state_paths",
                       return_value=(Path(tmp)/"voice.pid",path)), \
                 patch("hover_next.desktop.open_windows_app") as app, \
                 patch("hover_next.google_workspace.calendar_create_event") as event, \
                 redirect_stdout(output):
                self.assertEqual(diagnostics.quick_check(),0)
            app.assert_not_called()
            event.assert_not_called()
        self.assertIn("ACTIVO (PID 1234)",output.getvalue())
        self.assertIn("windows_app",output.getvalue())
        self.assertIn("spotify_play",output.getvalue())


class ReliableSpeechTests(unittest.TestCase):
    def test_natural_pause_does_not_split_whisper_command(self):
        vad=AdaptiveVad()
        speech=np.full(FRAME,0.008,dtype=np.float32)
        quiet=np.zeros(FRAME,dtype=np.float32)
        for _ in range(22):
            self.assertIsNone(vad.feed(speech))
        # Natural pause of 600ms between HOVER and its action.
        for _ in range(20):
            self.assertIsNone(vad.feed(quiet))
        for _ in range(15):
            self.assertIsNone(vad.feed(speech))
        for _ in range(24):
            self.assertIsNone(vad.feed(quiet))
        result=vad.feed(quiet)
        self.assertIsNotNone(result)

    def test_wake_to_execution_routes_known_actions_without_model_call(self):
        received=[]
        def dispatch(intent):
            received.append(intent)
            return "Acción realizada"
        dispatch._hover_accepts_intent=True
        dialogue=VoiceDialogue(dispatch,lambda *x:None,clock=lambda:100.0)
        with patch("hover_next.voice_coucou.publish"), \
             patch("hover_next.local_nlu.model_intent") as llm:
            self.assertEqual(dialogue.process("Hover, abre calculadora"),"action")
            self.assertEqual(dialogue.process("Hover, reproduce Spotify"),"action")
        self.assertEqual([i.action for i in received],
                         ["windows_app","spotify_play"])
        llm.assert_not_called()


if __name__=="__main__":
    unittest.main()

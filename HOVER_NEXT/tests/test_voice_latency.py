"""Performance regressions without network calls or Windows hardware."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock,patch

import numpy as np

from hover_next.audio_coucou import AdaptiveVad,FRAME
from hover_next.intent import Intent
from hover_next.voice_coucou import VoiceDialogue
from hover_next.recognizers import WhisperRecognizer
from hover_next import local_nlu


class LowerLatencyVADTests(unittest.TestCase):
    def test_fast_vad_finalizes_after_540ms(self):
        vad=AdaptiveVad()
        self.assertEqual(vad.hangover_frames,18)
        speech=np.full(FRAME,0.006,dtype=np.float32)
        silence=np.zeros(FRAME,dtype=np.float32)
        for _ in range(25):
            self.assertIsNone(vad.feed(speech))
        # Pauses shorter than 540ms must not fragment a voice command.
        for _ in range(17):
            self.assertIsNone(vad.feed(silence))
        complete=vad.feed(silence)
        self.assertIsInstance(complete,np.ndarray)
        self.assertGreater(len(complete),FRAME*25)

    def test_vad_still_ignores_short_noise(self):
        vad=AdaptiveVad()
        peak=np.zeros(FRAME,dtype=np.float32)
        peak[0]=0.3
        for _ in range(4):
            self.assertIsNone(vad.feed(peak))
        for _ in range(30):
            self.assertIsNone(vad.feed(np.zeros(FRAME,dtype=np.float32)))


class FastASRTests(unittest.TestCase):
    def setUp(self):
        self.rec=WhisperRecognizer.__new__(WhisperRecognizer)
        self.rec.model=MagicMock()
        self.rec.model.transcribe.return_value=([],None)

    def test_short_commands_can_explicitly_use_fast_whisper_beam(self):
        with patch.dict("os.environ",{"HOVER_WHISPER_BEAM":"3"}):
            self.rec.transcribe([0.01]*1600)
        kw=self.rec.model.transcribe.call_args.kwargs
        self.assertEqual(kw["beam_size"],3)
        self.assertEqual(kw["language"],"es")
        self.assertFalse(kw["condition_on_previous_text"])

    def test_higher_accuracy_beam_can_be_selected(self):
        import os
        with patch.dict("os.environ",{"HOVER_WHISPER_BEAM":"5"}):
            self.rec.transcribe([0.01]*1600)
        self.assertEqual(self.rec.model.transcribe.call_args.kwargs["beam_size"],5)

    def test_invalid_beam_falls_back_to_fast_default(self):
        with patch.dict("os.environ",{"HOVER_WHISPER_BEAM":"invalid"}):
            self.rec.transcribe([0.01]*1600)
        self.assertEqual(self.rec.model.transcribe.call_args.kwargs["beam_size"],2)

    def test_fast_default_beam_without_environment_override(self):
        with patch.dict("os.environ",{},clear=True):
            self.rec.transcribe([0.01]*1600)
        self.assertEqual(self.rec.model.transcribe.call_args.kwargs["beam_size"],2)


class FastIntentTests(unittest.TestCase):
    def test_wake_intent_is_parsed_once_for_production_executor(self):
        passed=[]
        def dispatcher(value):
            passed.append(value)
            return "Acción realizada"
        dispatcher._hover_accepts_intent=True
        dialog=VoiceDialogue(dispatcher,lambda *x:None,clock=lambda:100.0)
        intent=Intent("windows_app",args={"app":"calculator"})
        with patch("hover_next.voice_coucou.parse",return_value=intent) as parser, \
             patch("hover_next.voice_coucou.publish"):
            status=dialog.process("Hover, abre calculadora")
        self.assertEqual(status,"action")
        self.assertEqual(parser.call_count,1)
        self.assertEqual(passed,[intent])

    def test_existing_string_callbacks_remain_compatible(self):
        passed=[]
        dialog=VoiceDialogue(lambda value:passed.append(value) or "done",
                             lambda *x:None,clock=lambda:100.0)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(dialog.process("Hover, abre calculadora"),"action")
        self.assertEqual(passed,["abre calculadora"])

    def test_private_repo_still_receives_spoken_authorization(self):
        passed=[]
        def dispatcher(value):
            passed.append(value)
            return "done"
        dispatcher._hover_accepts_intent=True
        dialog=VoiceDialogue(dispatcher,lambda *x:None,clock=lambda:100.0)
        intent=Intent("create_private_repo",args={"name":"demo"})
        with patch("hover_next.voice_coucou.parse",return_value=intent), \
             patch("hover_next.voice_coucou.publish"):
            dialog._command("crea un repositorio privado que se llame demo")
        self.assertIsInstance(passed[0],str)
        self.assertIn("repo",passed[0])


class WarmNLUTests(unittest.TestCase):
    def test_warmup_loads_model_locally_without_executing_a_tool(self):
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=b"{}"
        with patch.dict("os.environ",{"HOVER_NLU":"auto",
                                       "HOVER_NLU_PREWARM":"1",
                                       "HOVER_NLU_MODEL":"qwen2.5:3b"}), \
             patch("hover_next.local_nlu.urlopen",return_value=mock) as url:
            self.assertTrue(local_nlu.warm_model())
        request=url.call_args.args[0]
        self.assertEqual(request.full_url,"http://127.0.0.1:11434/api/generate")
        payload=json.loads(request.data.decode())
        self.assertEqual(payload["prompt"],"")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["keep_alive"],"20m")
        self.assertNotIn("tools",payload)

    def test_warmup_is_disabled_by_default_on_shared_cpu(self):
        import os
        with patch.dict("os.environ",{"HOVER_NLU":"auto"},clear=True), \
             patch("hover_next.local_nlu.urlopen") as request:
            self.assertFalse(local_nlu.warm_model())
        request.assert_not_called()

    def test_warmup_can_be_disabled_to_save_memory(self):
        with patch.dict("os.environ",{"HOVER_NLU_PREWARM":"0"}), \
             patch("hover_next.local_nlu.urlopen") as call:
            self.assertFalse(local_nlu.warm_model())
        call.assert_not_called()


class GoogleWorkerIsolationTests(unittest.TestCase):
    def test_oauth_control_does_not_enter_asr_queue(self):
        source=(Path(__file__).resolve().parents[1]/
                "hover_next"/"voice_coucou.py").read_text(encoding="utf-8")
        self.assertIn("google_queue = Queue(maxsize=8)",source)
        self.assertIn("google_queue.put_nowait((job[0],job[1]))",source)
        self.assertIn('name="HOVER-GoogleOAuth"',source)
        self.assertIn("samples,queued_at=samples",source)
        self.assertIn("command_queue = Queue(maxsize=4)",source)
        self.assertIn('name="HOVER-Commands"',source)
        self.assertIn("command_queue.put_nowait((text,time.monotonic()))",source)
        self.assertNotIn('work_queue.put_nowait(("google"',source)
        self.assertIn('f"[latencia] cola=',source)
        self.assertIn('f"asr={asr_ms:.0f}ms "',source)
        self.assertIn('f"interpretacion_y_accion={action_ms:.0f}ms"',source)


if __name__=="__main__":
    unittest.main()

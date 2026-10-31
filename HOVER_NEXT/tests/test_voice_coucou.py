"""Realistic regression tests for the always-on HOVER voice engine."""
import unittest
from unittest.mock import patch

import numpy as np

from hover_next.audio_coucou import AdaptiveVad, FRAME, normalize_audio, resample_frame
from hover_next.voice_coucou import VoiceDialogue
from hover_next.voice_check import recognition_score


class VadTests(unittest.TestCase):
    def test_rejects_impulsive_mic_spikes(self):
        vad = AdaptiveVad(0.0008)
        frames = [np.zeros(FRAME,dtype=np.float32) for _ in range(90)]
        frames[20][0] = 0.35
        self.assertTrue(all(vad.feed(f) is None for f in frames))
        self.assertFalse(vad.active)

    def test_quiet_mic_remains_quiet(self):
        vad = AdaptiveVad()
        for _ in range(100):
            self.assertIsNone(vad.feed(np.full(FRAME,0.00001,dtype=np.float32)))
        self.assertFalse(vad.active)

    def test_user_voice_accepted_after_silence(self):
        vad = AdaptiveVad()
        output = []
        frames = ([np.zeros(FRAME,dtype=np.float32)]*15
                  + [np.full(FRAME,0.006,dtype=np.float32)]*35
                  + [np.zeros(FRAME,dtype=np.float32)]*30)
        for frame in frames:
            segment = vad.feed(frame)
            if segment is not None: output.append(segment)
        self.assertEqual(len(output),1)
        self.assertGreater(len(output[0]),FRAME*40)

    def test_low_energy_constant_voice_accepted(self):
        vad = AdaptiveVad(0.0006)
        segments = []
        for frame in ([np.full(FRAME,0.0012,dtype=np.float32)]*25
                      + [np.zeros(FRAME,dtype=np.float32)]*30):
            chunk=vad.feed(frame)
            if chunk is not None:segments.append(chunk)
        self.assertEqual(len(segments),1)

    def test_moderate_gain_without_clipping(self):
        signal=np.tile(np.linspace(-0.003,0.003,FRAME,dtype=np.float32),30)
        out=normalize_audio(signal)
        self.assertGreater(float(np.sqrt(np.mean(out*out))),0.004)
        self.assertLessEqual(float(np.max(np.abs(out))),0.95)

    def test_resampling_stereo_rate_to_mono_frame(self):
        frame=np.ones(1440,dtype=np.float32)*0.11
        out=resample_frame(frame)
        self.assertEqual(out.shape,(480,))
        self.assertAlmostEqual(float(out.mean()),0.11,places=5)


class MicrophoneSelectionTests(unittest.TestCase):
    def test_correct_windows_order_scores_highest(self):
        self.assertEqual(recognition_score("Hover abre calculadora"),1.0)
        self.assertEqual(recognition_score("abre la calculadora"),1.0)
    def test_noise_does_not_win_device_selection(self):
        self.assertLess(recognition_score("Subtitulos realizados por la comunidad de Amara.org"),0.5)
        self.assertLess(recognition_score("Hasta la proxima"),0.5)

class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.clock=[500.0]
        self.executed=[]
        self.dictated=[]
        self.d=VoiceDialogue(
            lambda x:self.executed.append(x) or "done",
            lambda provider,msg:self.dictated.append((provider,msg)) or "action",
            clock=lambda:self.clock[0])

    def test_standalone_hover_then_action(self):
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(self.d.process("Hover"),"wake")
            self.assertEqual(self.d.process("Abre calculadora"),"action")
        self.assertEqual(self.executed,["Abre calculadora"])

    def test_oye_hover_action(self):
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(self.d.process("Oye, jover, abre Google Drive"),"action")
        self.assertEqual(self.executed,["abre google drive"])

    def test_f8_fallback_bypasses_bad_wake_transcription(self):
        with patch("hover_next.voice_coucou.publish"):
            self.d.press_hotkey()
            self.assertEqual(self.d.process("abre Word"),"action")
        self.assertEqual(self.executed,["abre Word"])

    def test_ignores_ambient_speech(self):
        self.assertEqual(self.d.process("el profesor explico clustering"),"ignored")
        self.assertEqual(self.executed,[])

    def test_wake_timeout(self):
        with patch("hover_next.voice_coucou.publish"):
            self.d.process("Hover")
            self.clock[0]+=13
            self.assertEqual(self.d.process("abre calculadora"),"ignored")

    def test_dictation_without_second_wake(self):
        with patch("hover_next.voice_coucou.publish"):
            self.d.process("Hover abre Claude y escribe lo siguiente en un nuevo chat")
            self.assertEqual(self.d.dictation_provider,"claude")
            self.d.process("Resuelve el taller paso a paso")
        self.assertEqual(self.dictated,[("claude","Resuelve el taller paso a paso")])

if __name__=="__main__":
    unittest.main()

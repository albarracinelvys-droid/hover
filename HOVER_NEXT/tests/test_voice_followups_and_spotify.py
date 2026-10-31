"""Regression with actual Realtek/Whisper utterances and two-turn dialogue.

No GitHub mutation, real Spotify or Windows UI in automated tests.
"""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch

from hover_next.intent import parse
from hover_next.voice_coucou import VoiceDialogue
from hover_next.spoken_names import spoken_name
from hover_next.desktop import spotify_start_playback
from hover_next.app import voice_may_autocreate_private_repo


class SpokenNamesTests(unittest.TestCase):
    def test_normal_names(self):
        cases={
            ("Prueba uno","repo"):"prueba-uno",
            ("llámalo prueba uno","repo"):"prueba-uno",
            ("PRA1","repo"):"pra1",
            ("prueba uno en privado","repo"):"prueba-uno",
            ("Que se llama prueba1","txt"):"prueba1",
            ("prueba uno","folder"):"prueba uno",
        }
        for (text,kind),expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(spoken_name(text,kind),expected)

    def test_rejects_commands_and_unsafe_names(self):
        for text in ("borra todo","crea repositorio","reprodúcelo",
                     "../secreto","C:\\program files","cancela"):
            with self.subTest(text=text):
                self.assertEqual(spoken_name(text,"repo"),"")

    def test_new_repo_mishearing_variants(self):
        for text,name in (
            ("Hover. Crea un nuevo repositorio privado que ya me prueba uno","prueba-uno"),
            ("Hover, crea un repositorio privado en GitHub que ya me prueba uno","prueba-uno"),
            ("Hover, crea un nuevo repositorio privado en Github que llame PRA1","pra1"),
        ):
            with self.subTest(text=text):
                intent=parse(text)
                self.assertEqual(intent.action,"create_private_repo")
                self.assertEqual(intent.args["name"],name)

    def test_voice_auto_repo_fallback_is_not_silent(self):
        intent=parse("Hover crea un nuevo repositorio privado que ya me prueba uno")
        self.assertFalse(voice_may_autocreate_private_repo(
            "crea un nuevo repositorio privado que ya me prueba uno",intent))


class VoiceFollowupTests(unittest.TestCase):
    def setUp(self):
        self.now=[100.0]
        self.actions=[]
        self.d=VoiceDialogue(
            lambda phrase:self.actions.append((phrase,parse(phrase))) or "Executed",
            lambda provider,msg:"sent",
            clock=lambda:self.now[0],
        )
        self.patch=patch("hover_next.voice_coucou.publish")
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_repo_name_missing_then_followup(self):
        self.assertEqual(
            self.d.process("Hover, crea un nuevo repositorio privado que ya me prueba uno"),
            "waiting")
        self.assertEqual(self.d.pending_kind,"repo")
        self.assertFalse(self.actions)
        self.assertEqual(self.d.process("prueba uno"),"action")
        self.assertEqual(len(self.actions),1)
        self.assertEqual(self.actions[0][1].args["name"],"prueba-uno")

    def test_repo_missing_name_starts_dialogue(self):
        self.assertEqual(
            self.d.process("Hover, crea repositorio privado en GitHub"),"action")
        self.assertEqual(self.d.pending_kind,"repo")
        self.assertEqual(self.d.process("llámalo material nula"),"action")
        self.assertEqual(self.actions[-1][1].args["name"],"material-nula")

    def test_repo_name_expired_is_not_executed(self):
        self.d.process("Hover crea repositorio privado en Github")
        self.now[0]+=50
        self.assertEqual(self.d.process("prueba uno"),"ignored")
        self.assertEqual(len(self.actions),1)

    def test_safe_oye_txt_after_previous_hover(self):
        self.assertEqual(self.d.process("Hover abre calculadora"),"action")
        self.now[0]+=4
        self.assertEqual(self.d.process(
            "Oye, crea un TXT en la carpeta que tienes como atajo rápido."),"action")
        self.assertEqual(self.d.pending_kind,"txt")
        self.assertEqual(self.d.process("Que se llama prueba uno"),"action")
        self.assertEqual(self.actions[-1][1].action,"create_local")
        self.assertEqual(self.actions[-1][1].args,
                         {"kind":"txt","name":"prueba uno"})

    def test_new_oye_txt_request_overrides_pending_repo(self):
        self.d.process("Hover crea repositorio privado en Github")
        self.assertEqual(self.d.pending_kind,"repo")
        self.assertEqual(self.d.process(
            "Oye, crea un TXT en la carpeta que tienes como atajo rápido."),"action")
        self.assertEqual(self.d.pending_kind,"txt")
        self.assertEqual(self.d.process("prueba uno"),"action")
        self.assertEqual(self.actions[-1][1].action,"create_local")
        self.assertEqual(self.actions[-1][1].args["name"],"prueba uno")

    def test_no_oye_trigger_in_idle_without_hover(self):
        self.assertEqual(self.d.process(
            "Oye, crea un TXT en la carpeta que tienes como atajo rápido."),
            "ignored")
        self.assertEqual(self.actions,[])

    def test_spotify_followup_reprodúcelo(self):
        self.assertEqual(self.d.process("Hover. Reproduces Spotify."),"action")
        self.assertEqual(self.actions[-1][1].action,"spotify_play")
        self.now[0]+=6
        self.assertEqual(self.d.process("Reprodúcelo."),"action")
        self.assertEqual(self.actions[-1][1].action,"spotify_resume")

    def test_spotify_followup_expired_does_not_fire(self):
        self.d.process("Hover reproduce Spotify")
        self.now[0]+=47
        self.assertEqual(self.d.process("Reprodúcelo."),"ignored")
        self.assertEqual(len(self.actions),1)

    def test_cancel_pending_name(self):
        self.d.process("Hover crea TXT en mi carpeta")
        self.assertEqual(self.d.pending_kind,"txt")
        self.assertEqual(self.d.process("cancela"),"cancel")
        self.assertEqual(self.d.pending_kind,"")

    def test_new_full_wake_overrides_pending_name(self):
        self.d.process("Hover crea repositorio privado en Github")
        self.d.process("Hover abre calculadora")
        self.assertEqual(self.d.pending_kind,"")
        self.assertEqual(self.actions[-1][1].action,"windows_app")


class SpotifyExecutionTests(unittest.TestCase):
    def test_start_does_not_toggle_another_player_when_spotify_is_not_ready(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop.os.startfile",create=True) as start, \
             patch("hover_next.desktop._spotify_session_play",return_value="no_session"), \
             patch("hover_next.desktop.send_media_key") as key, \
             patch("time.sleep"):
            msg=spotify_start_playback(open_app=True)
        start.assert_called_once_with("spotify:")
        key.assert_not_called()
        self.assertIn("no detectó una sesión",msg)

    def test_followup_does_not_open_spotify_twice(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop.os.startfile",create=True) as start, \
             patch("hover_next.desktop._spotify_session_play",return_value="playing"), \
             patch("hover_next.desktop.send_media_key") as key:
            msg=spotify_start_playback(open_app=False)
        start.assert_not_called()
        key.assert_not_called()
        self.assertIn("Spotify",msg)

    def test_executor_uses_correct_playback_route(self):
        from hover_next.executor import Executor
        with tempfile.TemporaryDirectory() as d:
            e=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.spotify_start_playback",
                       return_value="Reproducción solicitada") as player:
                e.execute(parse("Hover reproduce Spotify"))
                e.execute(parse("Hover reprodúcelo"))
            self.assertEqual(player.call_args_list[0].kwargs,{"open_app":True,"play":True})
            self.assertEqual(player.call_args_list[1].kwargs,{"open_app":False})

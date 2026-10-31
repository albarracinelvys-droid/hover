"""Exact regression phrases transcribed on the user's Windows/Realtek logs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hover_next.intent import parse
from hover_next.voice_coucou import VoiceDialogue
from hover_next.executor import Executor

class RealLogRegressionTests(unittest.TestCase):
    def test_user_real_transcripts_are_actionable(self):
        cases = [
            ("ChatGPT.", "open_site", "chatgpt"),
            ("Hover. ChatGPT.", "open_site", "chatgpt"),
            ("Hover. Clout.", "open_site", "claude"),
            ("Abre Clouding.", "open_site", "claude"),
            ("Oye Hover. Abre Claude.", "open_site", "claude"),
            ("Oye Hover, abre ChatGPT", "open_site", "chatgpt"),
            ("Abre una nueva pestaña de Google.", "google_app", ""),
            ("Hover abre calculadora", "windows_app", ""),
            ("Hover abre Word", "office_new", ""),
        ]
        for transcript, expected_action, expected_provider in cases:
            with self.subTest(transcript=transcript):
                intent = parse(transcript)
                self.assertEqual(intent.action, expected_action)
                if expected_provider:
                    self.assertEqual(intent.provider, expected_provider)

    def test_short_wake_followed_by_chatgpt_runs(self):
        opened=[]
        clock=lambda: 120.0
        dialogue=VoiceDialogue(lambda command:opened.append(parse(command)) or "Abriendo",
                              lambda provider, prompt:None,clock=clock)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(dialogue.process("Oye Hover."),"wake")
            self.assertEqual(dialogue.process("ChatGPT."),"action")
        self.assertEqual(opened[0].action,"open_site")
        self.assertEqual(opened[0].provider,"chatgpt")

    def test_filler_does_not_cancel_command_window(self):
        clock=[120.0]
        opened=[]
        dialogue=VoiceDialogue(lambda command:opened.append(parse(command)) or "Abriendo",
                              lambda provider,prompt:None,clock=lambda:clock[0])
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(dialogue.process("Hover."),"wake")
            self.assertEqual(dialogue.process("Oye."),"waiting")
            clock[0]+=3
            self.assertEqual(dialogue.process("Abre Clouding."),"action")
        self.assertEqual(opened[0].provider,"claude")

    def test_real_executor_attempts_to_launch_google(self):
        with tempfile.TemporaryDirectory() as d:
            executor=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as google:
                response=executor.execute(parse("Abre una nueva pestaña de Google."))
            self.assertIn("google",response.lower())
            google.assert_called_once_with("https://www.google.com/")

    def test_real_executor_attempts_to_launch_chatgpt(self):
        with tempfile.TemporaryDirectory() as d:
            browser=MagicMock()
            executor=Executor(Path(d)/"config.json",browser=browser)
            with patch("hover_next.executor.webbrowser.open_new_tab",return_value=True) as web:
                response=executor.execute(parse("Hover. ChatGPT."))
            self.assertIn("chatgpt",response.lower())
            web.assert_called_once_with("https://chatgpt.com/")
            browser.page.assert_not_called()

    def test_real_executor_attempts_to_launch_claude(self):
        with tempfile.TemporaryDirectory() as d:
            executor=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.executor.webbrowser.open_new_tab",return_value=True) as web:
                response=executor.execute(parse("Abre Clouding."))
            self.assertIn("claude",response.lower())
            web.assert_called_once_with("https://claude.ai/new")

    def test_real_executor_starts_calculator(self):
        with tempfile.TemporaryDirectory() as d:
            executor=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.sys.platform","win32"), \
                 patch("hover_next.desktop.subprocess.Popen") as popen:
                response=executor.execute(parse("Hover abre calculadora"))
            self.assertEqual(response,"Calculadora abierta.")
            popen.assert_called_once_with(["calc.exe"],shell=False)

    def test_no_executed_command_for_ambient_phrase(self):
        for text in ("Oye.", "Hasta la próxima", "Subtítulos realizados por la comunidad de Amara.org"):
            with self.subTest(text=text):
                self.assertEqual(parse(text).action,"unknown")

if __name__ == "__main__":
    unittest.main()

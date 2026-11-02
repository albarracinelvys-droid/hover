"""Real transcription regression: open ChatGPT AND ask, never only open."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.chat_command import parse_chat_request
from hover_next.intent import parse
from hover_next.executor import Executor
from hover_next.voice_coucou import VoiceDialogue


class ChatQuestionTests(unittest.TestCase):
    def test_actual_first_whisper_transcription(self):
        phrase = "Oye Hover, abre chat, repete y pregúntale cómo está."
        request = parse_chat_request(phrase)
        self.assertIsNotNone(request)
        self.assertEqual(request.provider, "chatgpt")
        self.assertEqual(request.prompt, "¿Cómo estás?")
        intent = parse(phrase)
        self.assertEqual(intent.action, "chat_compose")
        self.assertEqual(intent.provider, "chatgpt")

    def test_actual_second_whisper_transcription(self):
        phrase = "Oye Hover. Abre ChatGPT y preguntarle cómo está."
        intent = parse(phrase)
        self.assertEqual(intent.action, "chat_compose")
        self.assertEqual(intent.provider, "chatgpt")
        self.assertEqual(intent.args["prompt"], "¿Cómo estás?")

    def test_direct_question_and_explicit_text_distinct(self):
        cases = [
            ("Hover abre ChatGPT y pregúntale qué es la automatización",
             "¿Qué es la automatización?"),
            ("Hover abre ChatGPT y dile hola", "hola"),
            ("Hover abre Claude y pregúntale por qué los motores se calientan",
             "¿Por qué los motores se calientan?"),
            ("Hover abre Claude y escríbele lo siguiente: Hola, ¿cómo vas?",
             "Hola, ¿cómo vas?"),
        ]
        for phrase, expected in cases:
            with self.subTest(phrase=phrase):
                intent = parse(phrase)
                self.assertEqual(intent.action, "chat_compose")
                self.assertEqual(intent.args["prompt"], expected)

    def test_no_question_uses_next_utterance_for_dictation(self):
        for text in ("Hover abre ChatGPT y pregúntale",
                     "Oye Hover abre ChatGPT y escribe lo siguiente"):
            with self.subTest(text=text):
                i = parse(text)
                self.assertEqual(i.action, "chat_prepare")
                self.assertFalse(i.args["prompt"])

    def test_not_ambient_mentions(self):
        for text in ("Vi un video de ChatGPT y pregúntale cómo está",
                     "La clase de ChatGPT trata de preguntarle cómo está",
                     "pregúntale cómo está"):
            with self.subTest(text=text):
                req = parse_chat_request(text)
                self.assertIsNone(req)

    def test_entire_voice_executor_path_sends_message(self):
        with tempfile.TemporaryDirectory() as d:
            fake_browser = MagicMock()
            fake_browser.prepare_chat.return_value="Pestaña nueva"
            fake_browser.send_prepared.return_value="Texto escrito; pulsado Enviar"
            ex = Executor(Path(d)/"config.json", browser=fake_browser)
            # The actual app.run_one also publishes UI states.
            from hover_next.app import run_one
            with patch("hover_next.app.publish"):
                result = run_one(
                    "Oye Hover. Abre ChatGPT y preguntarle cómo está.", ex)
            self.assertIsNotNone(result)
            fake_browser.prepare_chat.assert_called_once_with("chatgpt", "")
            fake_browser.send_prepared.assert_called_once_with(
                "chatgpt", "¿Cómo estás?")
            fake_browser.page.assert_not_called()

    def test_voice_dialogue_executes_composite_once(self):
        executed=[]
        d=VoiceDialogue(lambda command:executed.append(parse(command)) or "ok",
                        lambda provider, prompt:None, clock=lambda:100.0)
        with patch("hover_next.voice_coucou.publish"):
            result=d.process("Oye Hover, abre chat, repete y pregúntale cómo está")
        self.assertEqual(result, "action")
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].action, "chat_compose")
        self.assertEqual(d.dictation_provider, "")

class BrowserSubmissionTests(unittest.TestCase):
    def test_composer_receives_exact_text_and_enter(self):
        from hover_next.browser import BrowserBridge
        page = MagicMock()
        page.is_closed.return_value = False
        page.url = "https://chatgpt.com/"
        editor = MagicMock()
        editor.count.return_value = 1
        editor.is_visible.return_value = True
        page.locator.return_value.last = editor
        browser = BrowserBridge(Path("dummy"))
        browser._login_visible = MagicMock(return_value=False)
        browser._message_delivered = MagicMock(return_value=True)
        browser.prepared = ("chatgpt", page)
        result = browser.send_prepared("chatgpt", "¿Cómo estás?")
        editor.fill.assert_called_once_with("¿Cómo estás?", timeout=10000)
        editor.press.assert_called_once_with("Enter", timeout=10000)
        self.assertIn("confirmado", result)
        self.assertIsNone(browser.prepared)

    def test_not_sent_to_login_redirect(self):
        from hover_next.browser import BrowserBridge, BrowserUnavailable
        page = MagicMock()
        page.url = "https://auth.openai.com/"
        page.is_closed.return_value = False
        browser = BrowserBridge(Path("dummy"))
        browser.prepared = ("chatgpt", page)
        with self.assertRaises(BrowserUnavailable):
            browser.send_prepared("chatgpt", "¿Cómo estás?")
        page.locator.assert_not_called()

    def test_no_editor_reports_separate_profile(self):
        from hover_next.browser import BrowserBridge, BrowserUnavailable
        page = MagicMock()
        page.url = "https://chatgpt.com/"
        page.is_closed.return_value = False
        page.locator.return_value.last.count.return_value = 0
        browser = BrowserBridge(Path("dummy"))
        browser._login_visible = MagicMock(return_value=False)
        browser.prepared = ("chatgpt", page)
        with self.assertRaisesRegex(BrowserUnavailable, "Chrome independiente"):
            browser.send_prepared("chatgpt", "¿Cómo estás?")


if __name__ == "__main__":
    unittest.main()

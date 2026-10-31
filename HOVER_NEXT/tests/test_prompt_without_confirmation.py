"""Hands-free chat and materials lookup. Risky file/repo actions still confirm."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.app import run_one
from hover_next.executor import Executor
from hover_next.intent import parse
from hover_next.voice_coucou import VoiceDialogue


class NoPromptConfirmationTests(unittest.TestCase):
    def test_actual_voice_transcript_has_no_confirmation(self):
        intent = parse("Oye Hover. Preguntale a ChatGPT cómo está.")
        self.assertEqual(intent.action, "send_prompt")
        self.assertEqual(intent.provider, "chatgpt")
        self.assertEqual(intent.args["prompt"], "¿Cómo estás?")
        self.assertFalse(intent.requires_confirmation)

    def test_material_research_prompt_needs_no_si(self):
        examples = (
            "Hover pregúntale a Claude sobre rodamientos industriales",
            "Hover envíale a ChatGPT información sobre materiales SAP",
            "Hover dile a ChatGPT consulta de materiales de mantenimiento",
        )
        for utterance in examples:
            with self.subTest(utterance=utterance):
                parsed = parse(utterance)
                self.assertEqual(parsed.action, "send_prompt")
                self.assertFalse(parsed.requires_confirmation)

    def test_new_chat_prompt_and_composite_have_no_confirmation(self):
        intent = parse("Hover pregúntale a Claude en nuevo chat que es un rodamiento")
        # Legacy parser sometimes chooses send_prompt or new_chat_and_send,
        # but neither routine requires the terminal.
        self.assertIn(intent.action, ("send_prompt", "new_chat_and_send"))
        self.assertFalse(intent.requires_confirmation)
        composite = parse("Hover abre ChatGPT y pregúntale cómo está")
        self.assertEqual(composite.action, "chat_compose")
        self.assertFalse(composite.requires_confirmation)

    def test_google_search_no_confirmation(self):
        intent = parse("Hover busca rodamientos 6204 en Google")
        self.assertEqual(intent.action, "google_search")
        self.assertFalse(intent.requires_confirmation)

    def test_real_run_one_does_not_call_input_and_attempts_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            browser = MagicMock()
            browser.send_prompt.return_value = "Texto escrito en ChatGPT"
            executor = Executor(Path(tmp) / "config.json", browser=browser)
            with patch("builtins.input", side_effect=AssertionError("No debe pedir SI")), \
                 patch("hover_next.app.publish"):
                result = run_one("Oye Hover, pregúntale a ChatGPT cómo está", executor)
            self.assertEqual(result, "Texto escrito en ChatGPT")
            browser.send_prompt.assert_called_once_with(
                "chatgpt", "¿Cómo estás?", new=False)

    def test_full_voice_command_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            browser = MagicMock()
            browser.send_prompt.return_value = "Enviado a Chrome"
            executor = Executor(Path(tmp) / "config.json", browser=browser)
            dialogue = VoiceDialogue(
                lambda phrase: run_one(phrase, executor),
                lambda provider, prompt: "ok",
                clock=lambda: 120.0,
            )
            with patch("builtins.input", side_effect=AssertionError("No debe pedir SI")), \
                 patch("hover_next.app.publish"), \
                 patch("hover_next.voice_coucou.publish"):
                status = dialogue.process("Oye Hover, pregúntale a ChatGPT cómo está")
            self.assertEqual(status, "action")
            browser.send_prompt.assert_called_once()

    def test_direct_browser_prompt_reaches_verified_editor(self):
        from hover_next.browser import BrowserBridge
        with tempfile.TemporaryDirectory() as tmp:
            bridge = BrowserBridge(Path(tmp) / "profile")
            page = MagicMock()
            page.url = "https://chatgpt.com/"
            page.is_closed.return_value = False
            editor = MagicMock()
            editor.count.return_value = 1
            editor.is_visible.return_value = True
            page.locator.return_value.last = editor
            with patch.object(bridge, "page", return_value=page):
                result = bridge.send_prompt("chatgpt", "¿Cómo estás?", new=False)
            editor.fill.assert_called_once_with("¿Cómo estás?", timeout=10000)
            editor.press.assert_called_once_with("Enter", timeout=10000)
            self.assertIn("Enter", result)

    def test_browser_prompt_does_not_fake_success_on_login(self):
        from hover_next.browser import BrowserBridge, BrowserUnavailable
        with tempfile.TemporaryDirectory() as tmp:
            bridge = BrowserBridge(Path(tmp) / "profile")
            page = MagicMock()
            page.url = "https://auth.openai.com/login"
            page.is_closed.return_value = False
            with patch.object(bridge, "page", return_value=page):
                with self.assertRaises(BrowserUnavailable):
                    bridge.send_prompt("chatgpt", "¿Cómo estás?", new=False)
            page.locator.assert_not_called()

    def test_high_impact_operations_still_need_approval(self):
        for phrase in (
            "Hover crea un repositorio privado en GitHub llamado prueba-materiales",
            "Hover mueve el último archivo de Descargas a mi carpeta configurada",
            "Hover adjunta archivo financiero.pdf a Claude",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(parse(phrase).requires_confirmation)


if __name__ == "__main__":
    unittest.main()

"""All informational spoken questions default to Google, not local actions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.intent import parse
from hover_next.executor import Executor
from hover_next.voice_coucou import VoiceDialogue


class NaturalQuestionRoutingTests(unittest.TestCase):
    def test_information_phrases_go_to_google(self):
        phrases = [
            "Oye Hover, qué es un PLC",
            "Hover qué es la inteligencia artificial",
            "Hover cuál es la diferencia entre Python y C++",
            "Hover diferencia entre corriente alterna y corriente continua",
            "Hover qué diferencia hay entre un sensor y un transductor",
            "Hover cómo funciona un motor eléctrico",
            "Hover por qué se calientan los rodamientos",
            "Hover para qué sirve un transformador",
            "Hover quién inventó el transistor",
            "Hover dónde queda Rionegro Antioquia",
            "Hover cuándo se inventó internet",
            "Hover cuánto cuesta un ESP32",
            "Hover qué significa TPM en mantenimiento",
            "Hover compara Windows y Linux",
            "Hover explícame cómo funciona un PLC",
            "Hover dime la diferencia entre Java y JavaScript",
            "Hover investiga sistemas de automatización industrial",
            "Hover consulta precios de sensores en Colombia",
            "Hover averigua qué es el SAP PM",
            "Hover busca información sobre las industrias de Medellín",
            "Hover busca carros baratos",
            "Hover búscame materiales SAP",
            "Hover buscar C++",
            "Hover puedes crear un repositorio privado con GitHub",
            "Hover cómo crear un repositorio privado en GitHub llamado demo",
            "Hover cómo adjuntar un archivo a ChatGPT",
        ]
        for spoken in phrases:
            with self.subTest(spoken=spoken):
                intent = parse(spoken)
                self.assertEqual(intent.action, "google_search")
                self.assertTrue(intent.args["query"])
                self.assertFalse(intent.requires_confirmation)

    def test_translations_are_google_translate(self):
        cases = [
            ("Hover traduce buenos días al inglés", "buenos dias", "en"),
            ("Oye Hover traduce hello al español", "hello", "es"),
            ("Hover traduce motor eléctrico al francés", "motor electrico", "fr"),
            ("Hover cómo se dice mantenimiento en inglés", "mantenimiento", "en"),
            ("Hover traduce", "", "en"),
        ]
        for spoken, expected_text, expected_target in cases:
            with self.subTest(spoken=spoken):
                intent = parse(spoken)
                self.assertEqual(intent.action, "google_translate")
                self.assertEqual(intent.args["text"], expected_text)
                self.assertEqual(intent.args["target"], expected_target)
                self.assertFalse(intent.requires_confirmation)

    def test_preserve_action_commands(self):
        examples = {
            "Hover abre GitHub": "open_link",
            "Hover abre calculadora": "windows_app",
            "Hover abre ChatGPT y pregúntale cómo está": "chat_compose",
            "Hover crea repositorio privado llamado prueba-uno": "create_private_repo",
            "Hover crea un TXT en la carpeta favorita": "local_name_needed",
            "Hover reproduce Spotify": "spotify_play",
            "Hover abre una pestaña de Google y busca carro": "google_search",
            "Hover qué puedes hacer": "show_help",
            "Hover crea documento en Google": "google_app",
            "Hover siguiente canción": "media_key",
        }
        for spoken, action in examples.items():
            with self.subTest(spoken=spoken):
                self.assertEqual(parse(spoken).action, action)

    def test_search_does_not_execute_github(self):
        spoken = "Hover cómo crear un repositorio privado en GitHub llamado demo"
        i = parse(spoken)
        self.assertEqual(i.action, "google_search")
        self.assertNotEqual(i.action, "create_private_repo")

    def test_whisper_transcription_still_searches_correctly(self):
        cases = [
            ("Oye Hover, ¿cuál es la diferencia entre Excel y Google Sheets?",
             "google_search"),
            ("Hover, busca C++ en Google", "google_search"),
            ("Oye Hover, abre Google y busca Python", "google_search"),
        ]
        for spoken, expected in cases:
            with self.subTest(spoken=spoken):
                self.assertEqual(parse(spoken).action, expected)


class GoogleExecutionTests(unittest.TestCase):
    def test_actual_google_search_url(self):
        with tempfile.TemporaryDirectory() as td:
            executor = Executor(Path(td)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as opener:
                result=executor.execute(parse("Hover qué es un PLC"))
        opener.assert_called_once_with(
            "https://www.google.com/search?q=que+es+un+plc")
        self.assertIn("Buscando en Google", result)

    def test_google_translate_url(self):
        with tempfile.TemporaryDirectory() as td:
            executor=Executor(Path(td)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as opener:
                result=executor.execute(parse("Hover traduce buenos días al inglés"))
        url=opener.call_args.args[0]
        self.assertTrue(url.startswith("https://translate.google.com/?"))
        self.assertIn("tl=en",url)
        self.assertIn("text=buenos+dias",url)
        self.assertIn("Traductor",result)

    def test_google_queries_are_hands_free(self):
        with tempfile.TemporaryDirectory() as td:
            executor=Executor(Path(td)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True), \
                 patch("builtins.input",side_effect=AssertionError("No debe pedir SI")):
                output=executor.execute(parse(
                    "Hover cuál es la diferencia entre Word y Excel"))
        self.assertIn("Buscando",output)

    def test_voice_to_google_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            executor=Executor(Path(td)/"config.json",browser=MagicMock())
            from hover_next.app import run_one
            d=VoiceDialogue(lambda spoken:run_one(spoken,executor,voice_mode=True),
                            lambda provider,text:None)
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as opener, \
                 patch("hover_next.voice_coucou.publish"), \
                 patch("hover_next.app.publish"):
                result=d.process("Oye Hover, ¿qué es la electrónica industrial?")
            self.assertEqual(result,"action")
            self.assertIn("google.com/search?q=",opener.call_args.args[0])


if __name__=="__main__":
    unittest.main()

"""Regression tests for the exact Realtek/Whisper voice transcripts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.intent import parse
from hover_next.executor import Executor, confirm_intent
from hover_next.voice_coucou import VoiceDialogue


class SpokenSearchTests(unittest.TestCase):
    def test_exact_google_search_transcript(self):
        spoken = "Oye Hover. Busca iPhone en Google."
        intent = parse(spoken)
        self.assertEqual(intent.action, "google_search")
        self.assertEqual(intent.args["query"], "iphone")

    def test_search_variants(self):
        cases = [
            ("Hover busca precios de iPhone 15 en Google", "precios de iphone 15"),
            ("Hover búscame mantenimiento TPM en internet", "mantenimiento tpm"),
            ("Hover busca en Google sensores DS18B20", "sensores ds18b20"),
            ("Hover buscar Python en Google", "python"),
        ]
        for spoken, query in cases:
            with self.subTest(spoken=spoken):
                intent = parse(spoken)
                self.assertEqual(intent.action, "google_search")
                self.assertEqual(intent.args["query"], query)

    def test_google_query_reaches_default_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor = Executor(Path(tmp) / "config.json", browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab", return_value=True) as opened:
                message = executor.execute(parse("Oye Hover busca iPhone en Google"))
            self.assertIn("Buscando en Google", message)
            opened.assert_called_once_with("https://www.google.com/search?q=iphone")

    def test_search_escapes_special_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor = Executor(Path(tmp) / "config.json", browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab", return_value=True) as opened:
                executor.execute(parse("Hover busca C++ & Python en Google"))
            self.assertIn("c%2B%2B", opened.call_args.args[0].lower())
            self.assertIn("%26", opened.call_args.args[0])

    def test_garbled_search_not_guessed(self):
        self.assertNotEqual(
            parse("Hover busca y Mahindra's the iPhone in a little busca and Google").action,
            "google_search",
        )

    def test_full_voice_dialogue_triggers_search(self):
        actions=[]
        d=VoiceDialogue(lambda command: actions.append(parse(command)) or "ok",
                        lambda p,m: None, clock=lambda:200.0)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(d.process("Oye Hover. Busca iPhone en Google."), "action")
        self.assertEqual(actions[0].action, "google_search")


class SpokenPrivateRepoTests(unittest.TestCase):
    def test_actual_misheard_whisper_transcript(self):
        spoken = ("Oye Hover, sería uno de los requisitorios en Github "
                  "privado que se llama prueba uno.")
        intent = parse(spoken)
        self.assertEqual(intent.action, "create_private_repo")
        self.assertTrue(intent.requires_confirmation)
        self.assertEqual(intent.args["name"], "prueba-uno")

    def test_correctly_spoken_repo_command(self):
        intent = parse(
            "Hover crea un nuevo repositorio en GitHub privado que se llama prueba uno"
        )
        self.assertEqual(intent.action, "create_private_repo")
        self.assertEqual(intent.args["name"], "prueba-uno")
        self.assertTrue(intent.requires_confirmation)

    def test_no_creation_without_privacy_or_explicit_name(self):
        self.assertNotEqual(parse("Hover habla de los requisitorios en GitHub").action,
                            "create_private_repo")
        self.assertNotEqual(parse("Hover crea repositorios en Github").action,
                            "create_private_repo")
        self.assertEqual(
            parse("Hover crea repositorio privado en GitHub").action, "repo_name_needed")

    def test_confirm_exact_spoken_name(self):
        intent = parse("Oye Hover crea repositorio privado que se llama prueba uno")
        with patch("builtins.input", return_value="prueba-uno"):
            self.assertTrue(confirm_intent(intent))
        with patch("builtins.input", return_value="prueba"):
            self.assertFalse(confirm_intent(intent))

    def test_not_executed_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Executor(Path(tmp)/"config.json",browser=MagicMock())
            intent=parse("Oye Hover crea repositorio privado llamado prueba uno")
            with patch("hover_next.executor.subprocess.run") as run:
                response=exe.execute(intent,confirmed=False)
            self.assertIn("pendiente", response)
            run.assert_not_called()

    def test_confirmed_repo_requires_github_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Executor(Path(tmp)/"config.json",browser=MagicMock())
            intent=parse("Oye Hover crea repositorio privado llamado prueba uno")
            done=MagicMock(returncode=0,stdout="https://github.com/usuario/prueba-uno",stderr="")
            with patch("hover_next.executor.shutil.which",return_value="gh.exe"), \
                 patch("hover_next.executor.subprocess.run",return_value=done) as run:
                result=exe.execute(intent,confirmed=True)
            self.assertIn("prueba-uno", result)
            args=run.call_args.args[0]
            self.assertEqual(args[:4],["gh.exe","repo","create","prueba-uno"])
            self.assertIn("--private",args)
            self.assertNotIn("--public",args)

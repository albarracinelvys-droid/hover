"""Exact regression scenarios from user's October 31 Realtek speech log."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.intent import parse
from hover_next.voice_coucou import VoiceDialogue
from hover_next.executor import Executor
from hover_next.app import voice_may_autocreate_private_repo


class RecordedSpeechInterpretation(unittest.TestCase):
    def test_open_tab_and_search_car(self):
        cases = (
            ("Hover. Abre una pestaña de Google y busca carro.", "carro"),
            ("Oye Hover. Abre una presencia de Google y busca carros.", "carros"),
            ("Hover abre una página de Google y busca ruedas", "ruedas"),
            ("Hover abre Google y busca carro", "carro"),
            ("Hover abre una pestaña de Google y busca C++", "c++"),
        )
        for phrase, query in cases:
            with self.subTest(phrase=phrase):
                i = parse(phrase)
                self.assertEqual(i.action, "google_search")
                self.assertEqual(i.args["query"], query)
                self.assertFalse(i.requires_confirmation)

    def test_ambiguous_repo_does_not_open_github_or_create_by_guess(self):
        phrase = "Hover. Crea un tropo privado en GitHub que se llama y prueba uno."
        i = parse(phrase)
        self.assertEqual(i.action, "repo_name_needed")
        self.assertFalse(voice_may_autocreate_private_repo(phrase, i))

    def test_ambiguous_txt_solicits_name_not_file_creation(self):
        i = parse("Hover. Quería un archivo y texto.")
        self.assertEqual(i.action, "local_name_needed")
        self.assertEqual(i.args["kind"], "txt")
        self.assertNotEqual(i.action, "create_local")

    def test_ordinary_website_and_named_repo_still_work(self):
        self.assertEqual(parse("Hover abre GitHub").action,"open_link")
        good=parse("Hover crea un repositorio privado llamado prueba uno")
        self.assertEqual(good.action, "create_private_repo")
        self.assertEqual(good.args["name"],"prueba-uno")


class UserLogVoiceDialogue(unittest.TestCase):
    def setUp(self):
        self.t=[50.0]
        self.executed=[]
        self.dialogue=VoiceDialogue(
            lambda cmd:self.executed.append((cmd,parse(cmd))) or "done",
            lambda provider,text:"sent",
            clock=lambda:self.t[0])
        self.p=patch("hover_next.voice_coucou.publish")
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_compound_search_runs_browser_not_home(self):
        result=self.dialogue.process("Hover. Abre una pestaña de Google y busca carro.")
        self.assertEqual(result,"action")
        self.assertEqual(self.executed[-1][1].action,"google_search")
        with tempfile.TemporaryDirectory() as d:
            ex=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as open_tab:
                ex.execute(self.executed[-1][1])
            open_tab.assert_called_once_with("https://www.google.com/search?q=carro")

    def test_misheard_repo_enters_dialogue_without_creating(self):
        self.assertEqual(self.dialogue.process(
            "Hover. Crea un tropo privado en GitHub que se llama y prueba uno."),
            "action")
        self.assertEqual(self.dialogue.pending_kind,"repo")
        self.assertNotIn("create_private_repo",[intent.action for _,intent in self.executed])
        self.assertEqual(self.dialogue.process("prueba uno"),"action")
        self.assertEqual(self.executed[-1][1].action,"create_private_repo")
        self.assertEqual(self.executed[-1][1].args["name"],"prueba-uno")

    def test_misheard_txt_enters_dialogue_and_creates_after_name(self):
        self.assertEqual(self.dialogue.process("Hover. Quería un archivo y texto."),"action")
        self.assertEqual(self.dialogue.pending_kind,"txt")
        self.assertEqual(self.dialogue.process("prueba uno"),"action")
        self.assertEqual(self.executed[-1][1].action,"create_local")
        self.assertEqual(self.executed[-1][1].args,{"kind":"txt","name":"prueba uno"})

    def test_outside_wake_word_never_executes_misheard_requests(self):
        self.assertEqual(self.dialogue.process("Crea un tropo privado en GitHub"),"ignored")
        self.assertEqual(self.dialogue.process("Quería un archivo y texto"),"ignored")
        self.assertFalse(self.executed)


if __name__=="__main__":
    unittest.main()

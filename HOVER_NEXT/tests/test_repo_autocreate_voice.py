"""Exact Realtek utterance -> automatic private repo -> Chrome + Windhawk.

No real GitHub mutation or browsers in tests.
"""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.app import run_one, voice_may_autocreate_private_repo
from hover_next.executor import Executor
from hover_next.github_navigation import created_repo_url, show_repo
from hover_next.intent import parse, Intent


class VoiceRepoAutoCreateTests(unittest.TestCase):
    def test_exact_user_transcript_strips_privacy_suffix(self):
        spoken=("Oye Hover, crea un nuevo repositorio que se llame, "
                "prueba uno en privado.")
        intent=parse(spoken)
        self.assertEqual(intent.action,"create_private_repo")
        self.assertEqual(intent.args["name"],"prueba-uno")
        self.assertTrue(voice_may_autocreate_private_repo(spoken,intent))
        self.assertTrue(voice_may_autocreate_private_repo(
            "crea un nuevo repositorio que se llame, prueba uno en privado",intent))

    def test_private_descriptor_not_in_name_other_variants(self):
        cases=[
            ("Hover crea un repositorio privado llamado materia-nula","materia-nula"),
            ("Oye Hover crea repositorio que se llame prueba uno privado","prueba-uno"),
            ("Hover crea un repo que se llama prueba uno de forma privada","prueba-uno"),
            ("Hover crea un repositorio que se llama, demo como privado","demo"),
        ]
        for phrase,name in cases:
            with self.subTest(phrase=phrase):
                got=parse(phrase)
                self.assertEqual(got.action,"create_private_repo")
                self.assertEqual(got.args["name"],name)

    def test_auto_creation_only_for_clear_verbal_request(self):
        self.assertFalse(voice_may_autocreate_private_repo(
            "seria uno de los requisitorios privados llamado prueba uno",
            Intent("create_private_repo",args={"name":"prueba-uno"},
                   requires_confirmation=True)))
        self.assertFalse(voice_may_autocreate_private_repo(
            "compra dos productos",Intent("purchase",requires_confirmation=True)))
        self.assertFalse(voice_may_autocreate_private_repo(
            "crea repositorio publico llamado demo",
            Intent("create_private_repo",args={"name":"demo"},
                   requires_confirmation=True)))

    def test_voice_end_to_end_skips_dialog_and_opens_chrome(self):
        utterance="Oye Hover, crea un nuevo repositorio que se llame, prueba uno en privado."
        created=MagicMock(returncode=0,stdout="https://github.com/alguien/prueba-uno\n",stderr="")
        with tempfile.TemporaryDirectory() as d:
            executor=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.app.confirm_voice_intent",side_effect=AssertionError("No confirmation GUI")), \
                 patch("hover_next.app.confirm_intent",side_effect=AssertionError("No stdin confirmation")), \
                 patch("builtins.input",side_effect=AssertionError("No stdin input")), \
                 patch("hover_next.executor.shutil.which",return_value="gh.exe"), \
                 patch("hover_next.executor.subprocess.run",return_value=created) as gh, \
                 patch("hover_next.github_navigation.show_repo",return_value="Google Chrome") as chrome, \
                 patch("hover_next.ui_bridge.publish") as progress, \
                 patch("hover_next.app.publish"):
                output=run_one(utterance,executor,voice_mode=True)
        self.assertIn("prueba-uno",output)
        self.assertIn("Google Chrome",output)
        gh.assert_called_once()
        args=gh.call_args.args[0]
        self.assertEqual(args[:4],["gh.exe","repo","create","prueba-uno"])
        self.assertIn("--private",args)
        self.assertNotIn("--public",args)
        chrome.assert_called_once_with("https://github.com/alguien/prueba-uno")
        self.assertTrue(any("Abriendo Chrome" in str(x) for x in progress.call_args_list))

    def test_text_mode_still_needs_manual_approval(self):
        utterance="Hover crea un repositorio privado llamado prueba-uno"
        with tempfile.TemporaryDirectory() as d:
            e=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.app.confirm_intent",return_value=False) as confirm, \
                 patch("hover_next.app.publish"), \
                 patch("hover_next.executor.subprocess.run") as gh:
                result=run_one(utterance,e,voice_mode=False)
        self.assertIsNone(result)
        confirm.assert_called_once()
        gh.assert_not_called()

    def test_no_gh_means_no_claim_of_success(self):
        with tempfile.TemporaryDirectory() as d:
            e=Executor(Path(d)/"config.json",browser=MagicMock())
            with patch("hover_next.executor.shutil.which",return_value=None), \
                 patch("hover_next.app.publish"):
                result=run_one("Hover crea repositorio privado llamado prueba-uno",
                               e,voice_mode=True)
        self.assertIsNone(result)

    def test_repo_url_matches_created_name_and_domain(self):
        self.assertEqual(
            created_repo_url("✓ Created https://github.com/u/prueba-uno","prueba-uno"),
            "https://github.com/u/prueba-uno")
        self.assertEqual(created_repo_url("https://github.com/u/otro","prueba-uno"),"")
        self.assertEqual(created_repo_url("https://github.com.evil.io/u/prueba-uno","prueba-uno"),"")
        self.assertEqual(created_repo_url("https://github.com/u/prueba-uno/issue/1","prueba-uno"),
                         "https://github.com/u/prueba-uno")

    def test_chrome_launch_when_installed(self):
        with patch("hover_next.github_navigation._chrome_paths",
                   return_value=iter([Path("C:/Fake/chrome.exe")])), \
             patch("hover_next.github_navigation.Path.is_file",return_value=True), \
             patch("hover_next.github_navigation.subprocess.Popen") as proc:
            browser=show_repo("https://github.com/u/prueba-uno")
        self.assertEqual(browser,"Google Chrome")
        proc.assert_called_once_with(
            ["C:/Fake/chrome.exe","https://github.com/u/prueba-uno"],shell=False)

if __name__=="__main__":
    unittest.main()

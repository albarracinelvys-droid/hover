"""Regression: exact user logs, no stdin in speech thread, shared HOVER folder."""
from __future__ import annotations
import ctypes
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hover_next.app import run_one
from hover_next.executor import Executor, confirm_voice_intent
from hover_next.intent import parse
from hover_next.local_files import FavoriteFolderError, create_item, selected_folder
from hover_next.voice_coucou import run


class NativeVoiceConfirmationTests(unittest.TestCase):
    def test_approves_private_repo_with_gui_not_stdin(self):
        intent = parse("Hover, crea un repositorio privado llamado prueba1")
        messagebox = MagicMock(return_value=6)
        fake_user32 = SimpleNamespace(MessageBoxW=messagebox)
        with patch("hover_next.executor.sys.platform", "win32"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=fake_user32), create=True), \
             patch("builtins.input", side_effect=AssertionError("stdin must not be used")):
            self.assertTrue(confirm_voice_intent(intent))
        self.assertIn("prueba1", messagebox.call_args.args[1])

    def test_declines_private_repo_with_gui(self):
        intent = parse("Hover, crea un repositorio privado llamado prueba1")
        messagebox = MagicMock(return_value=7)
        fake_user32 = SimpleNamespace(MessageBoxW=messagebox)
        with patch("hover_next.executor.sys.platform", "win32"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=fake_user32), create=True), \
             patch("builtins.input", side_effect=AssertionError("stdin must not be used")):
            self.assertFalse(confirm_voice_intent(intent))

    def test_run_one_uses_gui_in_voice_mode(self):
        with tempfile.TemporaryDirectory() as d:
            browser = MagicMock()
            executor = Executor(Path(d)/"config.json", browser=browser)
            with patch("hover_next.app.confirm_voice_intent", return_value=False) as dialog, \
                 patch("hover_next.app.confirm_intent",side_effect=AssertionError("Wrong confirm")), \
                 patch("hover_next.app.publish"), \
                 patch("builtins.input", side_effect=AssertionError("stdin must not be used")):
                # Uncertain Whisper wording is NOT eligible for auto-create.
                self.assertIsNone(run_one(
                    "Hover sería uno de los requisitorios privados que se llama prueba1",
                    executor, voice_mode=True))
            dialog.assert_called_once()
            browser.close.assert_not_called()

    def test_chat_prompt_needs_no_gui_or_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            browser = MagicMock()
            browser.send_prompt.return_value = "Prompt enviado"
            executor = Executor(Path(d)/"config.json",browser=browser)
            with patch("hover_next.app.confirm_voice_intent",side_effect=AssertionError()), \
                 patch("hover_next.app.confirm_intent",side_effect=AssertionError()), \
                 patch("builtins.input",side_effect=AssertionError()), \
                 patch("hover_next.app.publish"):
                result=run_one("Hover pregúntale a ChatGPT cómo está",
                               executor, voice_mode=True)
            self.assertEqual(result, "Prompt enviado")


class NativeFavoriteFolderTests(unittest.TestCase):
    def test_utf16_file_from_windhawk_and_create_txt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            destination=root/"Folder"
            destination.mkdir()
            config=root/"HOVER"/"carpeta_favorita.txt"
            config.parent.mkdir()
            config.write_text(str(destination),encoding="utf-16")
            with patch.dict(os.environ,{"APPDATA":str(root)}):
                self.assertEqual(selected_folder({}),destination.resolve())
                result=create_item({},"txt","prueba1")
            self.assertIn("prueba1.txt",result)
            self.assertTrue((destination/"prueba1.txt").exists())

    def test_existing_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"prueba1.txt").write_text("Original",encoding="utf-8")
            root=p/"roaming"
            with patch.dict(os.environ,{"APPDATA":str(root)}):
                with self.assertRaises(FavoriteFolderError):
                    create_item({"folder":str(p)},"txt","prueba1")
            self.assertEqual((p/"prueba1.txt").read_text(encoding="utf-8"),"Original")

    def test_subfolder_creation_and_invalid_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with patch.dict(os.environ,{"APPDATA":str(p/"roaming")}):
                result=create_item({"folder":str(p)},"folder","prueba uno")
                self.assertIn("prueba uno",result)
                self.assertTrue((p/"prueba uno").is_dir())
                with self.assertRaises(ValueError):
                    create_item({"folder":str(p)},"folder","../exterior")

    def test_not_configured_does_not_write_anywhere(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ,{"APPDATA":str(Path(d)/"missing")}):
                with self.assertRaises(FavoriteFolderError):
                    create_item({},"txt","anything")

    def test_actual_utterances(self):
        cases=(
            ("Oye Hover. En la carpeta que tienes la anexada, crea un TXT "
             "que se llama prueba1.", "txt","prueba1"),
            ("Oye Hover, en la carpeta que tiene ese anexado, "
             "crea un documento Excel que se llame ProEva1.", "excel","proeva1"),
            ("Hover crea una subcarpeta llamada prueba uno","folder","prueba uno"),
        )
        for spoken,kind,name in cases:
            with self.subTest(spoken=spoken):
                intent=parse(spoken)
                self.assertEqual(intent.action,"create_local")
                self.assertEqual(intent.args,{"kind":kind,"name":name})
                self.assertFalse(intent.requires_confirmation)

    def test_google_doc_asr_ree(self):
        intent=parse("Oye Hover. En la carpeta que tenés anexada, "
                     "creé un documento en Google.")
        self.assertEqual(intent.action, "google_app")
        self.assertEqual(intent.args["service"],"google_docs_new")


class ThreadShutdownTests(unittest.TestCase):
    def test_microphone_shutdown_closes_browser_on_worker_not_main(self):
        browser=MagicMock()
        owning_thread=[]
        browser.close.side_effect=lambda:owning_thread.append(threading.current_thread().name)
        executor=SimpleNamespace(browser=browser)
        sounddevice=MagicMock()
        sounddevice.query_devices.return_value={
            "default_samplerate":44100.0, "name":"Realtek"
        }
        sounddevice.InputStream.side_effect=KeyboardInterrupt()
        recognizer=SimpleNamespace(name="Mock",transcribe=lambda data: "")
        with patch.dict(sys.modules,{"sounddevice":sounddevice}), \
             patch("hover_next.voice_coucou.create_recognizer",return_value=recognizer), \
             patch("hover_next.voice_coucou.publish"):
            run(executor,engine="auto",device=None)
        browser.close.assert_called_once()
        self.assertEqual(owning_thread,["HOVER-LocalASR"])

    def test_browser_close_ignores_already_terminated_chrome(self):
        from hover_next.browser import BrowserBridge
        with tempfile.TemporaryDirectory() as d:
            bridge=BrowserBridge(Path(d))
            bridge.context=MagicMock()
            bridge.context.close.side_effect=RuntimeError("TargetClosedError")
            bridge.p=MagicMock()
            bridge.p.stop.side_effect=RuntimeError("connection closed")
            bridge.close()
            self.assertIsNone(bridge.context)
            self.assertIsNone(bridge.p)
            bridge.close()


if __name__ == "__main__":
    unittest.main()

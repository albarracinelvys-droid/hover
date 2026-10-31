"""Regression cases from the user's real Whisper logs.

Never actually shut down Windows during tests. All system actions are mocked.
"""
import sys
import unittest
from unittest.mock import MagicMock,patch

from hover_next.intent import parse
from hover_next.voice_coucou import VoiceDialogue
from hover_next.voice_semantics import parse_flexible


class ShutdownVoiceTests(unittest.TestCase):
    def test_exact_user_goodbye_wake_shuts_down_without_confirmation(self):
        for spoken in ("Hover bye bye","Oye Hover, bye bye.",
                       "Hover by by","Hover bai bai",
                       "Hover apaga el equipo"):
            with self.subTest(spoken=spoken):
                command=parse(spoken)
                self.assertEqual(command.action,"pc_shutdown")
                self.assertFalse(command.requires_confirmation)

    def test_incidental_goodbye_does_not_shut_down(self):
        for spoken in ("bye bye", "dile bye bye a mi amigo",
                       "Hover, dile a ChatGPT bye bye",
                       "Hover busca bye bye en Google",
                       "Hola, bye bye"):
            if spoken == "bye bye":
                # Parsing a command string is intentionally context-free;
                # VoiceDialogue, not the parser, enforces the wake word.
                continue
            self.assertNotEqual(parse(spoken).action,"pc_shutdown")

    def test_voice_needs_hover_wake_before_goodbye(self):
        sent=[]
        d=VoiceDialogue(lambda x:sent.append(x) or "ok",lambda *a:None,clock=lambda:100)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(d.process("Bye bye"),"ignored")
            self.assertEqual(sent,[])
            self.assertEqual(d.process("Hover, bye bye"),"action")
        self.assertEqual(sent,["bye bye"])

    def test_run_one_bypasses_popup(self):
        from hover_next.app import run_one
        executor=MagicMock()
        with patch("hover_next.desktop.shutdown_windows",
                   return_value="Solicité apagar Windows") as shutdown, \
             patch("hover_next.app.confirm_voice_intent") as popup, \
             patch("hover_next.app.publish"):
            # Use a real executor method but bypass init/browser.
            from hover_next.executor import Executor
            executor.execute=Executor.execute.__get__(executor,Executor)
            result=run_one("Hover, bye bye",executor,voice_mode=True)
        self.assertIn("Windows",result)
        shutdown.assert_called_once_with()
        popup.assert_not_called()

    def test_windows_shutdown_command_is_non_forced(self):
        from hover_next.desktop import shutdown_windows
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop.subprocess.Popen") as start:
            result=shutdown_windows()
        start.assert_called_once_with(
            ["shutdown.exe","/s","/t","0"],shell=False)
        self.assertIn("Windows",result)
        self.assertNotIn("/f",start.call_args.args[0])

    def test_refuses_shutdown_on_other_platforms(self):
        from hover_next.desktop import shutdown_windows,ActionUnavailable
        with patch("hover_next.desktop.sys.platform","linux"):
            with self.assertRaises(ActionUnavailable):
                shutdown_windows()


class FlexibleAppVoiceTests(unittest.TestCase):
    def test_flexible_natural_phrases(self):
        checks=(
            ("Hover, ábreme el Paint","windows_app","paint"),
            ("Hover, abre pint","windows_app","paint"),
            ("Oye Hover, puedes abrir el explorador de archivos","windows_app","explorer"),
            ("Hover, inicia Visual Studio Code","windows_app","vscode"),
            ("Hover, ejecuta VS Code","windows_app","vscode"),
            ("Hover, cierra el explorador de archivos","pc_close_window","explorer"),
            ("Hover, sierra explorer","pc_close_window","explorer"),
            ("Hover, cierra Visual Studio Code","pc_close_window","vscode"),
            ("Hover, termina el bloc de notas","pc_close_window","notepad"),
            ("Hover, por favor abre la calculadora","windows_app","calculator"),
            ("Hover, ciérrame la ventana activa","pc_close_window","foreground"),
        )
        for spoken,action,value in checks:
            with self.subTest(spoken=spoken):
                i=parse(spoken)
                self.assertEqual(i.action,action)
                self.assertIn(value,i.args.values())

    def test_natural_file_requests_do_not_require_a_fixed_phrase(self):
        cases=(
            ("Hover, hazme una carpeta llamada ejercicios en documentos",
             "folder","ejercicios","documents"),
            ("Hover, quiero que me crees un Excel llamado inventario en documentos",
             "excel","inventario","documents"),
            ("Hover, podrías crear una carpeta llamada planes en el escritorio",
             "folder","planes","desktop"),
            ("Hover, prepara un Word llamado minuta en el escritorio",
             "word","minuta","desktop"),
        )
        for spoken,kind,name,folder in cases:
            with self.subTest(spoken=spoken):
                intent=parse(spoken)
                self.assertEqual(intent.action,"pc_create")
                self.assertEqual(intent.args,{
                    "kind":kind,"name":name,"location":folder})
                self.assertFalse(intent.requires_confirmation)

    def test_unreliable_english_gibberish_does_not_close_anything(self):
        for transcript in ("sierra explorer the truth",
                           "sierra exploraordertools",
                           "cierra todo del sistema",
                           "apaga por favor",
                           "que significa cierra word"):
            with self.subTest(transcript=transcript):
                self.assertNotIn(parse(transcript).action,
                                 ("pc_close_window","pc_shutdown"))

    def test_semantic_resolver_never_runs_shell(self):
        self.assertIsNone(parse_flexible("ejecuta powershell borra c"))
        self.assertIsNone(parse_flexible("termina chrome.exe"))
        self.assertIsNone(parse_flexible("elimina sistema c"))
        self.assertIsNone(parse_flexible("como cerrar word"))

    def test_whisper_keeps_spanish_language_and_pc_vocabulary(self):
        from hover_next.recognizers import WhisperRecognizer
        recognizer=WhisperRecognizer.__new__(WhisperRecognizer)
        recognizer.model=MagicMock()
        recognizer.model.transcribe.return_value=([],None)
        recognizer.transcribe([0.01,0.02])
        kwargs=recognizer.model.transcribe.call_args.kwargs
        self.assertEqual(kwargs["language"],"es")
        self.assertIn("explorador de archivos",kwargs["initial_prompt"])
        self.assertIn("Paint",kwargs["initial_prompt"])
        self.assertIn("bye bye",kwargs["initial_prompt"])


if __name__=="__main__":
    unittest.main()

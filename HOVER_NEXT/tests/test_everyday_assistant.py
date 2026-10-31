import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.intent import parse, Intent
from hover_next.wake import extract_wake
from hover_next.chat_command import parse_chat_request
from hover_next.executor import Executor
from hover_next.desktop import open_document, ActionUnavailable, open_google

class SiriStyleCommandTests(unittest.TestCase):
    def test_hover_without_oye(self):
        self.assertEqual(extract_wake("Hover, abre calculadora"),"abre calculadora")
        self.assertEqual(extract_wake("Hover"),"")
        self.assertEqual(extract_wake("Oye Hover abre Word"),"abre word")

    def test_windows_calculator(self):
        i=parse("Hover, abre la calculadora")
        self.assertEqual(i.action,"windows_app")
        self.assertEqual(i.args["app"],"calculator")

    def test_word_new(self):
        i=parse("Hover, abre un nuevo documento de Word")
        self.assertEqual(i.action,"office_new")
        self.assertEqual(i.args["kind"],"word")

    def test_excel_powerpoint(self):
        self.assertEqual(parse("Hover, crea un libro de Excel").args["kind"],"excel")
        self.assertEqual(parse("Hover, abre PowerPoint").args["kind"],"powerpoint")

    def test_this_document(self):
        i=parse("Hover, abre este documento")
        self.assertEqual(i.action,"open_document")
        self.assertEqual(i.args["name"],"")

    def test_named_document(self):
        i=parse("Hover, abre el documento llamado taller de programación")
        self.assertEqual(i.action,"open_document")
        self.assertIn("taller",i.args["name"])

    def test_google_services(self):
        cases={
            "Hover, abre Google Drive":"google_drive",
            "Hover, crea un documento de Google":"google_docs_new",
            "Hover, crea una hoja de cálculo":"google_sheets_new",
            "Hover, abre Gmail":"google_gmail",
            "Hover, abre mi calendario":"google_calendar",
            "Hover, abre Google Maps":"google_maps",
            "Hover, abre Google Meet":"google_meet",
            "Hover, abre Google Keep":"google_keep",
            "Hover, abre YouTube":"google_youtube",
        }
        for utterance,service in cases.items():
            with self.subTest(utterance=utterance):
                i=parse(utterance)
                self.assertEqual(i.action,"google_app")
                self.assertEqual(i.args["service"],service)

    def test_cloud_new_chat_with_message(self):
        phrase="Hover, abre una nueva pestaña de Cloud y escríbele lo siguiente: Necesito un resumen técnico."
        request=parse_chat_request(phrase)
        self.assertIsNotNone(request)
        self.assertEqual(request.provider,"claude")
        self.assertEqual(request.prompt,"Necesito un resumen técnico.")
        self.assertEqual(parse(phrase).action,"chat_compose")

    def test_chatgpt_zap_wait_for_dictation(self):
        i=parse("Hover, abre ChatGPT y en proyecto Zap escribe lo siguiente en un nuevo chat")
        self.assertEqual(i.action,"chat_prepare")
        self.assertEqual(i.provider,"chatgpt")
        self.assertEqual(i.args["project"],"zap")
        self.assertFalse(i.args["prompt"])

    def test_chatgpt_zap_direct_message(self):
        i=parse("Hover, abre ChatGPT en proyecto Zap y escribe lo siguiente: Diseña una prueba de PLC.")
        self.assertEqual(i.action,"chat_compose")
        self.assertEqual(i.args["project"],"zap")
        self.assertEqual(i.args["prompt"],"Diseña una prueba de PLC.")

    def test_ambient_mention_never_opens_google(self):
        self.assertEqual(parse("hoy hablamos de google docs en clase").action,"unknown")

    def test_missing_project_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            browser=MagicMock()
            e=Executor(Path(d)/"config.json",browser=browser)
            i=parse("Hover abre ChatGPT en proyecto Zap escribe lo siguiente: hola")
            with self.assertRaises(ValueError):
                e.execute(i)
            browser.prepare_chat.assert_not_called()

    def test_chat_prepare_and_send(self):
        with tempfile.TemporaryDirectory() as d:
            browser=MagicMock()
            browser.prepare_chat.return_value="Pestaña abierta"
            browser.send_prepared.return_value="Escribí el mensaje"
            e=Executor(Path(d)/"config.json",browser=browser)
            i=parse("Hover, abre Cloud y escríbele lo siguiente: Hola")
            self.assertEqual(e.execute(i),"Escribí el mensaje")
            browser.prepare_chat.assert_called_once_with("claude","")
            browser.send_prepared.assert_called_once_with("claude","Hola")

    def test_open_google_allowlist(self):
        with patch("hover_next.desktop.webbrowser.open_new_tab",return_value=True) as opened:
            result=open_google("google_gmail")
        self.assertIn("gmail",result)
        self.assertEqual(opened.call_args.args[0],"https://mail.google.com/mail/u/0/#inbox")
        with self.assertRaises(ActionUnavailable):
            open_google("arbitrary_url")

    def test_document_disallows_exe(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._selected_explorer_path",return_value=Path("C:/a/program.exe")):
            with self.assertRaises(ActionUnavailable):
                open_document()

if __name__=="__main__":
    unittest.main()

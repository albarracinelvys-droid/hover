"""HOVER Google OAuth, DPAPI, personal account search and Windhawk IPC tests.

No network calls, private Google content, browser login or actual token
material is used in the test suite.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch

from hover_next import google_auth as auth
from hover_next import google_ipc as ipc
from hover_next import google_workspace as ws
from hover_next.intent import parse
from hover_next.executor import Executor


class OAuthLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.old_folder=auth.TOKEN_FOLDER
        self.old_client=auth.CLIENT
        auth.TOKEN_FOLDER=self.base/"token"
        auth.CLIENT=self.base/"google_oauth_client.json"
        self.addCleanup(setattr,auth,"TOKEN_FOLDER",self.old_folder)
        self.addCleanup(setattr,auth,"CLIENT",self.old_client)

    def test_isolated_minimal_google_scopes(self):
        self.assertEqual(set(auth.SERVICES),{"drive","calendar","gmail","docs"})
        self.assertIn("drive.metadata.readonly",auth.SCOPES["drive"][0])
        self.assertEqual(len(auth.SCOPES["gmail"]),1)
        self.assertTrue(auth.SCOPES["gmail"][0].endswith("gmail.readonly"))
        self.assertTrue(auth.SCOPES["calendar"][0].endswith("calendar.events.readonly"))
        self.assertTrue(any(x.endswith("drive.file") for x in auth.SCOPES["docs"]))
        self.assertNotIn("https://www.googleapis.com/auth/drive",sum(
            [list(x) for x in auth.SCOPES.values()],[]))

    def test_no_client_json_before_user_adds_own_credentials(self):
        with self.assertRaisesRegex(auth.GoogleAuthError,"google_oauth_client.json"):
            auth._client_path()

    def test_invalid_client_is_rejected(self):
        auth.CLIENT.write_text('{"web":{"client_id":"should-not-accept"}}',encoding="utf-8")
        with self.assertRaisesRegex(auth.GoogleAuthError,"no es válido"):
            auth._client_path()

    def test_dpapi_encrypted_storage_never_leaves_json_token(self):
        credentials=MagicMock()
        credentials.to_json.return_value=json.dumps({
            "access_token":"DO-NOT-COMMIT-THIS-TOKEN",
            "refresh_token":"PRIVATE-REFRESH-TOKEN"})
        def protect(plaintext):
            self.assertIn(b"PRIVATE-REFRESH-TOKEN",plaintext)
            return b"BINARY-DPAPI-CIPHERTEXT"
        with patch.object(auth,"_protect",side_effect=protect):
            auth._save("drive",credentials)
        saved=auth._token_path("drive").read_bytes()
        self.assertEqual(saved,b"BINARY-DPAPI-CIPHERTEXT")
        self.assertNotIn(b"PRIVATE",saved)
        self.assertTrue(auth.connected("drive"))
        self.assertFalse(auth.connected("gmail"))
        auth.disconnect("drive")
        self.assertFalse(auth.connected("drive"))

    def test_only_allowlisted_service_files(self):
        with self.assertRaises(ValueError):
            auth._token_path("../token")
        with self.assertRaises(ValueError):
            auth.disconnect("outlook")

    def test_multiple_service_disconnection(self):
        for service in auth.SERVICES:
            auth._token_path(service).parent.mkdir(parents=True,exist_ok=True)
            auth._token_path(service).write_bytes(b"ciphertext")
        auth.disconnect("all")
        self.assertFalse(any(auth.status().values()))

    def test_install_flow_requests_exact_service_scopes(self):
        auth.CLIENT.write_text(
            '{"installed":{"client_id":"fake-client-id","client_secret":"not-real"}}',
            encoding="utf-8")
        fake_flow=MagicMock()
        fake_flow.run_local_server.return_value=MagicMock(
            to_json=lambda:'{"token":"private"}')
        with patch.object(auth,"sys") as sysfake, \
             patch.object(auth,"_save") as save, \
             patch.dict("sys.modules",{
                 "google_auth_oauthlib":MagicMock(),
                 "google_auth_oauthlib.flow":MagicMock(
                     InstalledAppFlow=MagicMock(
                         from_client_secrets_file=MagicMock(return_value=fake_flow)))
             }):
            sysfake.platform="win32"
            auth.connect("calendar")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0],"calendar")


class GoogleVoiceTests(unittest.TestCase):
    def test_connect_disconnect_and_status(self):
        cases={
            "Hover conecta Google":("google_connect","all"),
            "Hover conecta mi cuenta de Gmail":("google_connect","gmail"),
            "Hover conecta Google Drive":("google_connect","drive"),
            "Hover desconecta Google Calendar":("google_disconnect","calendar"),
            "Hover conecta Google Docs":("google_connect","docs"),
        }
        for spoken,(action,service) in cases.items():
            with self.subTest(spoken=spoken):
                i=parse(spoken)
                self.assertEqual(i.action,action)
                self.assertEqual(i.args["service"],service)
        self.assertEqual(parse("Hover estado de Google").action,"google_status")

    def test_personal_search_is_not_public_search(self):
        cases={
            "Hover busca factura en mi Drive":"drive",
            "Hover busca reuniones en mi calendario":"calendar",
            "Hover busca facturas en mi Gmail":"gmail",
            "Hover busca contrato en mi cuenta de Google":"all",
            "Hover revisa mis correos sobre mantenimiento":"gmail",
            "Hover busca documentos de calibración en mi Drive":"drive",
        }
        for text,source in cases.items():
            with self.subTest(text=text):
                intent=parse(text)
                self.assertEqual(intent.action,"google_personal_search")
                self.assertEqual(intent.args["source"],source)
                self.assertFalse(intent.requires_confirmation)

    def test_private_info_not_forwarded_to_ai_without_confirmation(self):
        i=parse("Hover busca informe en mi Drive y envíalo a ChatGPT")
        self.assertEqual(i.action,"google_share_ai")
        self.assertEqual(i.args["provider"],"chatgpt")
        self.assertTrue(i.requires_confirmation)
        i=parse("Hover busca proyectos en mi Gmail y envíalo a Claude")
        self.assertEqual(i.action,"google_share_ai")
        self.assertTrue(i.requires_confirmation)
        with tempfile.TemporaryDirectory() as td:
            browser=MagicMock()
            exe=Executor(Path(td)/"config.json",browser=browser)
            result=exe.execute(i,confirmed=False)
            self.assertIn("pendiente",result)
            browser.prepare_chat.assert_not_called()

    def test_doc_create_vs_default_google_docs_open(self):
        self.assertEqual(
            parse("Hover crea documento de Google llamado informe semanal").action,
            "google_create_doc")
        self.assertEqual(parse("Hover crea documento en Google").action,"google_app")

    def test_public_questions_still_search_google(self):
        self.assertEqual(parse("Hover qué es un PLC").action,"google_search")
        self.assertEqual(parse("Hover abre ChatGPT y pregúntale cómo estás").action,
                         "chat_compose")
        self.assertEqual(parse("Hover abre Word").action,"office_new")

    def test_private_search_results_never_auto_send(self):
        with tempfile.TemporaryDirectory() as td:
            browser=MagicMock()
            exe=Executor(Path(td)/"config.json",browser=browser)
            item=ws.Item("Drive","Informe","BOM mantenimiento",
                         "https://drive.google.com/file/d/abc/view")
            with patch("hover_next.google_workspace.search_all",
                       return_value=([item],[])), \
                 patch("hover_next.desktop.webbrowser.open_new_tab",
                       return_value=True):
                output=exe.execute(parse("Hover busca informe en mi Drive"))
            self.assertIn("1 resultados",output)
            browser.send_prepared.assert_not_called()


class GoogleApiTests(unittest.TestCase):
    def test_drive_query_escapes_single_quote_and_backslash(self):
        q=ws._drive_query("Bob's \\materiales")
        self.assertIn("Bob\\'s",q)
        self.assertIn("\\\\materiales",q)
        self.assertIn("trashed = false",q)

    def test_restrict_external_links(self):
        self.assertTrue(ws._safe_link("https://drive.google.com/file/d/abc/view"))
        self.assertFalse(ws._safe_link("https://google.com.evil.net/x"))
        self.assertFalse(ws._safe_link("http://docs.google.com/"))
        self.assertFalse(ws._safe_link("javascript:alert(1)"))

    def test_drive_search_scopes_results_to_google_host(self):
        api=MagicMock()
        api.files.return_value.list.return_value.execute.return_value={
            "files":[{"id":"file1","name":"Informe",
                      "webViewLink":"https://docs.google.com/document/d/file1/edit"},
                     {"id":"file2","name":"Malo",
                      "webViewLink":"https://evil.net/private"}]
        }
        with patch("hover_next.google_workspace._service",return_value=api):
            matches=ws.drive_search("informe",limit=5)
        self.assertEqual(matches[0].url,
                         "https://docs.google.com/document/d/file1/edit")
        self.assertEqual(matches[1].url,"")
        self.assertIn("pageSize",api.files.return_value.list.call_args.kwargs)

    def test_docs_create_uses_minimal_docs_client(self):
        service=MagicMock()
        service.documents.return_value.create.return_value.execute.return_value={
            "documentId":"1234567890abcDEF"}
        with patch("hover_next.google_workspace._service",return_value=service):
            doc=ws.docs_create("Informe de mantenimiento")
        self.assertEqual(doc.title,"Informe de mantenimiento")
        self.assertTrue(doc.url.startswith("https://docs.google.com/document/d/"))


class GoogleIpcTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old=(ipc.BASE,ipc.CONTROL,ipc.STATUS)
        base=Path(self.temp.name)
        ipc.BASE=base
        ipc.CONTROL=base/"google_control.txt"
        ipc.STATUS=base/"google_status.tsv"
        self.addCleanup(self.restore)

    def restore(self):
        ipc.BASE,ipc.CONTROL,ipc.STATUS=self.old

    def test_valid_command_only_once(self):
        ipc.CONTROL.write_text("connect drive\n",encoding="utf-8")
        self.assertEqual(ipc.poll_control(),("connect","drive"))
        self.assertIsNone(ipc.poll_control())

    def test_reject_injected_commands(self):
        for text in ("connect ../secret","connect gmail && del C:",
                     "disconnect all\nconnect drive","hello"):
            with self.subTest(text=text):
                ipc.CONTROL.write_text(text,encoding="utf-8")
                self.assertIsNone(ipc.poll_control())

    def test_reject_google_account_mismatch(self):
        with patch("hover_next.google_auth._client_path",return_value=Path("oauth.json")), \
             patch("hover_next.google_auth.status",side_effect=[
             {"drive":True,"calendar":False,"gmail":False,"docs":False},
             {"drive":True,"calendar":False,"gmail":False,"docs":False}]), \
             patch("hover_next.google_auth.account_email",
                   side_effect=["owner@example.com","other@example.com"]), \
             patch("hover_next.google_auth.connect") as connect, \
             patch("hover_next.google_auth.disconnect") as disconnect, \
             patch("hover_next.google_ipc.write_status"), \
             patch("hover_next.ui_bridge.publish"):
            result=ipc.execute_control("connect","calendar")
        connect.assert_called_once_with("calendar")
        disconnect.assert_called_once_with("calendar")
        self.assertIn("calendar:",result)

    def test_drop_new_token_when_identity_lookup_fails(self):
        with patch("hover_next.google_auth._client_path",return_value=Path("oauth.json")), \
             patch("hover_next.google_auth.status",return_value={
             "drive":False,"calendar":False,"gmail":False,"docs":False}), \
             patch("hover_next.google_auth.connect") as connect, \
             patch("hover_next.google_auth.account_email",
                   side_effect=RuntimeError("userinfo unavailable")), \
             patch("hover_next.google_auth.disconnect") as disconnect, \
             patch("hover_next.google_ipc.write_status"), \
             patch("hover_next.ui_bridge.publish"):
            result=ipc.execute_control("connect","gmail")
        connect.assert_called_once_with("gmail")
        disconnect.assert_called_once_with("gmail")
        self.assertIn("gmail:",result)

    def test_missing_oauth_client_reports_once_and_skips_all_services(self):
        with patch("hover_next.google_auth._client_path",
                   side_effect=auth.GoogleAuthError("missing")), \
             patch("hover_next.google_auth.connect") as connect, \
             patch("hover_next.google_ipc.write_status") as report, \
             patch("hover_next.ui_bridge.publish") as ui:
            message=ipc.execute_control("connect","all")
        self.assertIn("FALTA CLIENTE OAUTH",message)
        connect.assert_not_called()
        report.assert_called_once()
        ui.assert_called_once()

    def test_status_has_only_flags_and_message_not_tokens(self):
        with patch("hover_next.google_auth.status",return_value={
             "drive":True,"calendar":False,"gmail":True,"docs":False}):
            ipc.write_status("Google\tOK\nPrivado")
        data=ipc.STATUS.read_text(encoding="utf-8")
        self.assertTrue(data.startswith("1\t0\t1\t0\t"))
        self.assertNotIn("\n",data)


if __name__=="__main__":
    unittest.main()

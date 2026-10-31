"""Regression for the user's exact WinError 5 / 32 and missing OAuth log.

Tests simulate contention without modifying Windhawk's real Temp directory.
"""
import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next import ui_bridge
from hover_next import google_auth
from hover_next import google_ipc


class WindhawkLockRecoveryTests(unittest.TestCase):
    def test_replace_retries_windows_access_denied_and_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"voice_ui.txt"
            replace=os.replace
            calls=[]
            def transient(src,dst):
                calls.append(Path(src))
                if len(calls)<3:
                    raise PermissionError(13,"locked by Windhawk")
                return replace(src,dst)
            with patch.object(ui_bridge,"bridge_file",return_value=file), \
                 patch.object(ui_bridge.os,"replace",side_effect=transient), \
                 patch.object(ui_bridge.time,"sleep") as sleep:
                success=ui_bridge.publish("thinking","Google conectando",3)
            self.assertTrue(success)
            self.assertEqual(len(calls),3)
            self.assertIn("Google conectando",file.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(td).glob("*.tmp")),[])
            self.assertEqual(sleep.call_count,2)

    def test_permanent_lock_is_nonfatal_and_throttles_console_warning(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"voice_ui.txt"
            with patch.object(ui_bridge,"bridge_file",return_value=target), \
                 patch.object(ui_bridge.os,"replace",
                              side_effect=PermissionError(13,"locked")), \
                 patch.object(ui_bridge.time,"sleep"), \
                 patch.object(ui_bridge,"_LAST_WARNING",0.0), \
                 patch("builtins.print") as report:
                self.assertFalse(ui_bridge.publish("error","OAuth error"))
                self.assertFalse(ui_bridge.publish("error","OAuth error again"))
            self.assertEqual(report.call_count,1)
            self.assertEqual(list(Path(td).glob("*.tmp")),[])

    def test_two_publishes_use_distinct_temporary_files(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"voice_ui.txt"
            observed=[]
            real=os.replace
            def record(src,dst):
                observed.append(str(src))
                return real(src,dst)
            with patch.object(ui_bridge,"bridge_file",return_value=p), \
                 patch.object(ui_bridge.os,"replace",side_effect=record):
                self.assertTrue(ui_bridge.publish("idle","first"))
                self.assertTrue(ui_bridge.publish("ok","second"))
            self.assertEqual(len(observed),2)
            self.assertNotEqual(observed[0],observed[1])


class GoogleSetupRecoveryTests(unittest.TestCase):
    def test_missing_client_aborts_all_without_retries(self):
        with patch.object(google_auth,"_client_path",
                          side_effect=google_auth.GoogleAuthError("missing")), \
             patch.object(google_auth,"CLIENT",Path("/no-such-oauth.json")), \
             patch.object(google_auth,"connect") as connect, \
             patch.object(google_ipc,"write_status") as status, \
             patch("hover_next.ui_bridge.publish"):
            message=google_ipc.execute_control("connect","all")
        self.assertIn("FALTA CLIENTE OAUTH",message)
        connect.assert_not_called()
        status.assert_called_once()

    def test_invalid_desktop_client_reports_invalid_not_missing(self):
        with tempfile.TemporaryDirectory() as td:
            client=Path(td)/"google_oauth_client.json"
            client.write_text('{"web":{}}',encoding="utf-8")
            with patch.object(google_auth,"_client_path",
                              side_effect=google_auth.GoogleAuthError("invalid")), \
                 patch.object(google_auth,"CLIENT",client), \
                 patch.object(google_auth,"connect") as connect, \
                 patch.object(google_ipc,"write_status"), \
                 patch("hover_next.ui_bridge.publish"):
                message=google_ipc.execute_control("connect","all")
        self.assertIn("INVALIDO",message)
        connect.assert_not_called()


class SingleInstanceTests(unittest.TestCase):
    def test_non_windows_is_passthrough_for_ci(self):
        from hover_next.single_instance import voice_instance
        with patch("hover_next.single_instance.sys.platform","linux"):
            with voice_instance():
                self.assertTrue(True)

    def test_second_voice_process_exits_without_starting_recognizer(self):
        from hover_next.app import main
        from hover_next.single_instance import AlreadyRunning
        executor=MagicMock()
        executor.config={}
        with patch("sys.argv",["hover","--voice"]), \
             patch("hover_next.app.Executor",return_value=executor), \
             patch("hover_next.single_instance.voice_instance",
                   side_effect=AlreadyRunning("HOVER already running")), \
             patch("hover_next.voice_coucou.run") as voice, \
             patch("builtins.print"):
            main()
        voice.assert_not_called()

if __name__=="__main__":
    unittest.main()

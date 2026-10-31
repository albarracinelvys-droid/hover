"""Regression checks for HOVER's one-click OAuth setup.

No live tokens, Google accounts, or Windows APIs are accessed by these tests.
"""
import unittest
from unittest.mock import patch

from hover_next import google_cli


class GoogleCliTests(unittest.TestCase):
    def test_dpapi_preflight_succeeds(self):
        with patch("hover_next.google_cli.google_auth._client_path"), \
             patch("hover_next.google_cli.google_auth._protect",
                   return_value=b"encrypted"), \
             patch("hover_next.google_cli.google_auth._unprotect",
                   return_value=b"HOVER Windows DPAPI self-test"):
            self.assertTrue(google_cli._check_prerequisites())

    def test_dpapi_preflight_detects_missing_pywin32(self):
        with patch("hover_next.google_cli.google_auth._client_path"), \
             patch("hover_next.google_cli.google_auth._protect",
                   side_effect=ImportError("win32crypt")):
            self.assertFalse(google_cli._check_prerequisites())

    def test_cannot_claim_success_without_saved_token(self):
        state={"drive":False,"calendar":False,"gmail":False,"docs":False}
        with patch("hover_next.google_cli._check_prerequisites",return_value=True), \
             patch("hover_next.google_cli.google_ipc.execute_control",
                   return_value="drive conectado como usuario@example.com"), \
             patch("hover_next.google_cli.google_auth.status",
                   return_value=state):
            self.assertEqual(google_cli.main(["--service","drive"]),1)

    def test_success_only_when_result_and_state_match(self):
        state={"drive":True,"calendar":False,"gmail":False,"docs":False}
        with patch("hover_next.google_cli._check_prerequisites",return_value=True), \
             patch("hover_next.google_cli.google_ipc.execute_control",
                   return_value="drive conectado como usuario@example.com"), \
             patch("hover_next.google_cli.google_auth.status",
                   return_value=state):
            self.assertEqual(google_cli.main(["--service","drive"]),0)

    def test_existing_token_with_failed_reauth_is_not_success(self):
        state={"drive":True,"calendar":False,"gmail":False,"docs":False}
        with patch("hover_next.google_cli._check_prerequisites",return_value=True), \
             patch("hover_next.google_cli.google_ipc.execute_control",
                   return_value="drive: GoogleAuthError"), \
             patch("hover_next.google_cli.google_auth.status",
                   return_value=state):
            self.assertEqual(google_cli.main(["--service","drive"]),1)

    def test_status_does_not_initiate_oauth(self):
        state={"drive":False,"calendar":False,"gmail":False,"docs":False}
        with patch("hover_next.google_cli.google_ipc.execute_control") as connect, \
             patch("hover_next.google_cli.google_auth.status",
                   return_value=state):
            self.assertEqual(google_cli.main(["--status"]),0)
        connect.assert_not_called()


if __name__=="__main__":
    unittest.main()

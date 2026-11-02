"""Regression tests grounded in the 2026-11-01 HOVER voice log.

No real web login, microphone, Spotify API, or network calls are performed.
"""
from __future__ import annotations
from pathlib import Path
import unittest
from unittest.mock import MagicMock,patch

from hover_next.intent import parse
from hover_next.browser import BrowserBridge,BrowserUnavailable


class VoiceRecognitionRegression(unittest.TestCase):
    def test_misheard_calculador_opens_calculator_without_ollama(self):
        with patch("hover_next.local_nlu.model_intent",
                   side_effect=AssertionError("Ollama must not be required")):
            action=parse("Oye Hover, abre el calculador.")
        self.assertEqual(action.action,"windows_app")
        self.assertEqual(action.args["app"],"calculator")

    def test_fuzzy_alias_is_never_used_for_closing_unknown_process(self):
        with patch("hover_next.local_nlu.model_intent",return_value=None):
            action=parse("Oye Hover, cierra el calculador.")
        self.assertEqual(action.action,"unknown")


class ChatAcknowledgmentRegression(unittest.TestCase):
    def _browser(self):
        page=MagicMock()
        page.url="https://chatgpt.com/"
        page.is_closed.return_value=False
        item=MagicMock()
        item.count.return_value=1
        item.is_visible.return_value=True
        page.locator.return_value.last=item
        browser=BrowserBridge(Path("test-browser-profile"))
        browser.prepared=("chatgpt",page)
        return browser,page,item

    def test_enter_alone_is_not_evidence_chatgpt_sent_message(self):
        b,page,editor=self._browser()
        with patch.object(b,"_login_visible",return_value=False), \
             patch.object(b,"_message_delivered",return_value=False):
            with self.assertRaisesRegex(BrowserUnavailable,"NO confirmó"):
                b.send_prepared("chatgpt","¿Cómo estás?")
        editor.fill.assert_called_once()
        editor.press.assert_called_once_with("Enter",timeout=10000)
        self.assertIsNotNone(b.prepared)

    def test_shows_login_insead_of_silently_typing_into_guest_session(self):
        b,page,editor=self._browser()
        with patch.object(b,"_login_visible",return_value=True):
            with self.assertRaisesRegex(BrowserUnavailable,"Inicia sesión"):
                b.send_prepared("chatgpt","¿Cómo estás?")
        editor.fill.assert_not_called()
        editor.press.assert_not_called()

    def test_sends_only_when_user_bubble_is_confirmed(self):
        b,page,editor=self._browser()
        with patch.object(b,"_login_visible",return_value=False), \
             patch.object(b,"_message_delivered",return_value=True) as check:
            result=b.send_prepared("chatgpt","¿Cómo estás?")
        self.assertIn("confirmado",result)
        self.assertIsNone(b.prepared)
        check.assert_called_once()
        self.assertEqual(check.call_args.args[2],"¿Cómo estás?")

    def test_manual_login_helper_uses_hovers_profile_without_credentials(self):
        from hover_next import chat_login
        bridge=MagicMock()
        page=MagicMock(url="https://chatgpt.com/")
        bridge.page.return_value=page
        bridge._login_visible.return_value=False
        with patch("hover_next.chat_login.BrowserBridge",return_value=bridge) as cls, \
             patch("hover_next.chat_login.linked_google_email",
                   return_value="linked@example.com"), \
             patch("builtins.input",return_value=""):
            self.assertEqual(chat_login.main(),0)
        args=cls.call_args.args
        self.assertEqual(args[0].name,"chrome_profile")
        bridge.close.assert_called_once()

    def test_login_helper_does_not_claim_verified_account_while_login_visible(self):
        from hover_next import chat_login
        bridge=MagicMock()
        bridge.page.return_value=MagicMock(url="https://chatgpt.com/")
        bridge._login_visible.return_value=True
        with patch("hover_next.chat_login.BrowserBridge",return_value=bridge), \
             patch("hover_next.chat_login.linked_google_email",
                   return_value="linked@example.com"), \
             patch("builtins.input",return_value=""):
            self.assertEqual(chat_login.main(),2)
        bridge.close.assert_called_once()

    def test_actual_dom_user_bubble_must_grow_and_match_text(self):
        b,page,editor=self._browser()
        self.assertTrue(b._message_delivered(
            page,"chatgpt","¿Cómo estás?",before=1))
        kwargs=page.wait_for_function.call_args.kwargs
        self.assertEqual(kwargs["arg"]["selector"],
                         '[data-message-author-role="user"]')
        self.assertEqual(kwargs["arg"]["previous"],1)
        self.assertEqual(kwargs["arg"]["text"],"¿Cómo estás?")
        self.assertEqual(kwargs["timeout"],4500)
        page.wait_for_function.side_effect=TimeoutError()
        self.assertFalse(b._message_delivered(
            page,"chatgpt","¿Cómo estás?",before=1))


class SpotifyUIRegression(unittest.TestCase):
    def test_late_cover_retry_and_bridge_playback_controls_in_windhawk(self):
        source=Path(__file__).resolve().parents[2]/(
            "HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp")
        s=source.read_text(encoding="utf-8")
        self.assertIn('if(name==g_currentCoverName && g_albumCover)return;',s)
        self.assertIn('if(tick-lastAttempt<500)return;',s)
        self.assertIn('WriteBridgeCommand("play")',s)
        self.assertIn('WriteBridgeCommand("next")',s)
        self.assertIn('WriteBridgeCommand("prev")',s)


if __name__=="__main__":
    unittest.main()

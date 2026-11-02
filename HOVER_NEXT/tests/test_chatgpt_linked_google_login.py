"""Linked Google identity -> official ChatGPT Google-login regressions.

No actual Google or ChatGPT accounts are accessed in these tests.
"""
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock,patch
from pathlib import Path

from hover_next.browser import BrowserBridge,BrowserUnavailable
from hover_next import chat_login


class GmailIdentityTests(TestCase):
    def test_reads_verified_linked_gmail_identity_without_token_reuse(self):
        with patch("hover_next.google_auth.connected",return_value=True) as connected, \
             patch("hover_next.google_auth.account_email",
                   return_value="linked@example.com") as account:
            self.assertEqual(chat_login.linked_google_email(),"linked@example.com")
        connected.assert_called_once_with("gmail")
        account.assert_called_once_with("gmail")

    def test_absent_gmail_requires_explicit_connection_not_other_google_account(self):
        with patch("hover_next.google_auth.connected",return_value=False), \
             patch("hover_next.google_auth.account_email") as email:
            with self.assertRaisesRegex(BrowserUnavailable,"Gmail no está vinculado"):
                chat_login.linked_google_email()
        email.assert_not_called()

    def test_invalid_or_unverifiable_linked_email_fails_closed(self):
        with patch("hover_next.google_auth.connected",return_value=True), \
             patch("hover_next.google_auth.account_email",
                   return_value="not an email"):
            with self.assertRaisesRegex(BrowserUnavailable,"no es válido"):
                chat_login.linked_google_email()
        with patch("hover_next.google_auth.connected",return_value=True), \
             patch("hover_next.google_auth.account_email",
                   side_effect=RuntimeError("Secret oauth response")):
            with self.assertRaisesRegex(BrowserUnavailable,"No pude verificar"):
                chat_login.linked_google_email()


class ChatGPTGoogleSignInTests(TestCase):
    def _setup(self,url="https://auth.openai.com/login",google_url=None):
        bridge=BrowserBridge(Path("test-profile"))
        page=MagicMock()
        page.url=url
        page.is_closed.return_value=False
        btn=MagicMock()
        btn.count.return_value=1
        btn.is_visible.return_value=True
        page.get_by_role.return_value.first=btn
        context=MagicMock()
        context.pages=[page]
        bridge.context=context
        google_page=None
        if google_url is not None:
            google_page=MagicMock()
            google_page.url=google_url
            account=MagicMock()
            account.count.return_value=1
            account.is_visible.return_value=True
            google_page.get_by_text.return_value.first=account
            context.pages.append(google_page)
        return bridge,page,btn,google_page

    def test_open_official_chatgpt_google_login_and_select_only_exact_gmail(self):
        bridge,page,button,google=self._setup(
            google_url="https://accounts.google.com/v3/signin/accountchooser")
        step=bridge.begin_google_sign_in(page,"linked@example.com")
        self.assertEqual(step,"selected")
        page.goto.assert_called_once_with(
            "https://chatgpt.com/auth/login",
            wait_until="domcontentloaded",timeout=30000)
        button.click.assert_called_once_with(timeout=6000)
        google.get_by_text.assert_called_once_with(
            "linked@example.com",exact=True)
        google.get_by_text.return_value.first.click.assert_called_once_with(
            timeout=5000)

    def test_never_choose_account_on_non_google_site(self):
        bridge,page,button,suspicious=self._setup(
            google_url="https://accounts.google.com.evil.invalid/login")
        result=bridge.begin_google_sign_in(page,"linked@example.com")
        self.assertEqual(result,"google_opened")
        suspicious.get_by_text.assert_not_called()

    def test_google_account_not_visible_means_user_chooses(self):
        bridge,page,button,google=self._setup(
            google_url="https://accounts.google.com/v3/signin/accountchooser")
        google.get_by_text.return_value.first.count.return_value=0
        self.assertEqual(
            bridge.begin_google_sign_in(page,"linked@example.com"),
            "google_opened")
        google.get_by_text.return_value.first.click.assert_not_called()

    def test_missing_continue_with_google_leaves_manual_sign_in(self):
        bridge,page,button,_=self._setup()
        button.count.return_value=0
        self.assertEqual(bridge.begin_google_sign_in(
            page,"linked@example.com"),"manual")
        button.click.assert_not_called()

    def test_never_open_unknown_authentication_host(self):
        bridge,page,button,_=self._setup(
            url="https://auth.openai.com.evil.invalid/login")
        with self.assertRaisesRegex(BrowserUnavailable,"oficial"):
            bridge.begin_google_sign_in(page,"linked@example.com")
        button.click.assert_not_called()

    def test_no_email_cannot_begin_google_flow(self):
        bridge,page,button,_=self._setup()
        with self.assertRaisesRegex(BrowserUnavailable,"Gmail vinculado"):
            bridge.begin_google_sign_in(page,"invalid")
        page.goto.assert_not_called()

    def test_voice_can_start_google_login_but_does_not_send_prompt(self):
        bridge,page,button,_=self._setup("https://chatgpt.com/")
        bridge.context.new_page.return_value=page
        with patch.object(bridge,"_login_visible",return_value=True), \
             patch("hover_next.google_auth.connected",return_value=True), \
             patch("hover_next.google_auth.account_email",
                   return_value="linked@example.com"), \
             patch.object(bridge,"begin_google_sign_in",
                          return_value="google_opened") as google:
            result=bridge.prepare_chat("chatgpt")
        self.assertIn("Confirma",result)
        google.assert_called_once_with(page,"linked@example.com")
        self.assertIsNotNone(bridge.prepared)
        page.locator.assert_not_called()

    def test_never_import_browser_cookies_or_workspace_oauth_token(self):
        from hover_next import browser
        import inspect
        source=inspect.getsource(browser.BrowserBridge.begin_google_sign_in)
        self.assertNotIn("credentials(",source)
        self.assertNotIn("access_token",source)
        self.assertNotIn("cookie",source.lower().replace("cookies", ""))
        self.assertNotIn("localStorage",source)


if __name__=="__main__":
    import unittest
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.projects import get_project_url, read_project_links, valid_project_url
from hover_next.executor import Executor
from hover_next.intent import parse

class ProjectShortcutTests(unittest.TestCase):
    def test_allowed_project_urls(self):
        self.assertTrue(valid_project_url("chatgpt", "https://chatgpt.com/g/g-p-a1-zap"))
        self.assertTrue(valid_project_url("claude", "https://claude.ai/project/1234abcd"))
        self.assertFalse(valid_project_url("chatgpt", "https://chatgpt.com/c/abc"))
        self.assertFalse(valid_project_url("claude", "https://attacker.example/project/uuid"))
        self.assertFalse(valid_project_url("chatgpt", "file:///C:/something"))

    def test_native_tsv_links(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/"projects.tsv"
            store.write_text(
                "chatgpt\tZap\thttps://chatgpt.com/g/g-p-a1-zap\n"
                "claude\tNotas\thttps://claude.ai/project/abc123\n"
                "chatgpt\tMal\thttps://example.com/steal\n",encoding="utf-8")
            projects=read_project_links(store)
            self.assertEqual(projects["chatgpt"]["zap"],"https://chatgpt.com/g/g-p-a1-zap")
            self.assertEqual(projects["claude"]["notas"],"https://claude.ai/project/abc123")
            self.assertNotIn("mal",projects["chatgpt"])

    def test_shortcut_overrides_old_config(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/"projects.tsv"
            store.write_text("chatgpt\tZap\thttps://chatgpt.com/g/g-p-updated-zap\n",encoding="utf-8")
            with patch("hover_next.projects.project_store",return_value=store):
                url=get_project_url(
                    {"projects":{"chatgpt":{"zap":"https://chatgpt.com/g/g-p-old-zap"}}},
                    "chatgpt","ZAP")
            self.assertEqual(url,"https://chatgpt.com/g/g-p-updated-zap")

    def test_voice_opens_project_saved_from_shortcuts(self):
        with tempfile.TemporaryDirectory() as d:
            browser=MagicMock()
            e=Executor(Path(d)/"config.json",browser=browser)
            intent=parse("Hover abre ChatGPT en proyecto Zap escribe lo siguiente: Hola")
            with patch("hover_next.projects.get_project_url",
                       return_value="https://chatgpt.com/g/g-p-a1-zap"):
                e.execute(intent)
            browser.prepare_chat.assert_called_once_with(
                "chatgpt","https://chatgpt.com/g/g-p-a1-zap")
            browser.send_prepared.assert_called_once_with("chatgpt","Hola")

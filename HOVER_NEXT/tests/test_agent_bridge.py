"""No microphone, browser session or cloud credentials required."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hover_next.ui_bridge import publish, status_page
from hover_next.agent import AgentUnavailable, run_agent

class BridgeTests(unittest.TestCase):
    def test_writes_windhawk_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "voice_ui.txt"
            with patch("hover_next.ui_bridge.bridge_file", return_value=target):
                self.assertTrue(publish("thinking", "Oye\tHover\nprueba", 3))
            fields = target.read_text(encoding="utf-8").split("\t", 3)
            # Voice state is now deliberately compact, without a tab request.
            self.assertEqual(fields[1], "quiet-thinking")
            self.assertEqual(fields[2], "-1")
            self.assertEqual(fields[3], "Oye Hover prueba")
    def test_page_routing(self):
        self.assertEqual(status_page("spotify_play"), 0)
        self.assertEqual(status_page("new_chat"), 3)
        self.assertEqual(status_page("show_pc"), 4)
        self.assertEqual(status_page("agent_ask"), -1)
    def test_rejects_unknown_visual_state(self):
        with self.assertRaises(ValueError):
            publish("speaking", "HOVER no habla")

class AgentTests(unittest.TestCase):
    def test_unconfigured_write_is_blocked(self):
        with self.assertRaises(AgentUnavailable):
            run_agent("crea algo", {"agent_provider":"codex"}, write=True)
    def test_codex_read_only_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            r = MagicMock(returncode=0,stdout="Respuesta segura",stderr="")
            with patch("hover_next.agent.shutil.which", return_value="codex"), patch("hover_next.agent.subprocess.run",return_value=r) as sp:
                result = run_agent("explica Python", {"agent_provider":"codex","agent_workspace":d})
            self.assertEqual(result,"Respuesta segura")
            args = sp.call_args.args[0]
            self.assertIn("read-only", args)
            self.assertEqual(sp.call_args.kwargs["input"],"explica Python")
            self.assertFalse(sp.call_args.kwargs["shell"])
    def test_codex_write_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as d:
            r=MagicMock(returncode=0,stdout="Terminado",stderr="")
            with patch("hover_next.agent.shutil.which",return_value="codex"), patch("hover_next.agent.subprocess.run",return_value=r) as sp:
                run_agent("crea un archivo de prueba",{"agent_provider":"codex","agent_workspace":d},write=True)
            args=sp.call_args.args[0]
            self.assertEqual(args[args.index("--sandbox")+1],"workspace-write")
            self.assertNotIn("danger-full-access",args)
    def test_claude_write_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("hover_next.agent.shutil.which",return_value="claude"):
                with self.assertRaises(AgentUnavailable):
                    run_agent("editar",{"agent_provider":"claude","agent_workspace":d},write=True)

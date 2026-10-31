"""Regression tests for a compact Windhawk notch and background Explorer closes."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from hover_next import ui_bridge,pc_files
from hover_next.intent import parse


def windows_mock():
    gui=MagicMock()
    con=MagicMock(WM_CLOSE=16)
    # 10 is the focused PowerShell terminal; Explorer is 20/30 behind.
    gui.GetForegroundWindow.return_value=10
    gui.EnumWindows.side_effect=lambda callback,data: [
        callback(hwnd,data) for hwnd in (10,20,30)]
    titles={10:"Windows PowerShell",20:"Descargas",30:"Documentos"}
    classes={10:"ConsoleWindowClass",20:"CabinetWClass",30:"CabinetWClass"}
    gui.GetWindowText.side_effect=lambda hwnd:titles[hwnd]
    gui.GetClassName.side_effect=lambda hwnd:classes[hwnd]
    gui.IsWindowVisible.return_value=True
    return gui,con


class CompactNotchTests(unittest.TestCase):
    def test_all_voice_statuses_are_quiet_and_never_request_an_expanded_page(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"voice_ui.txt"
            with patch("hover_next.ui_bridge.bridge_file",return_value=target):
                for state,page in (("listening",3),("thinking",4),
                                   ("ok",3),("error",1),("idle",4)):
                    with self.subTest(state=state):
                        self.assertTrue(ui_bridge.publish(state,"Prueba",page))
                        serial,wire,p,description=target.read_text(
                            encoding="utf-8").split("\t")
                        self.assertEqual(p,"-1")
                        self.assertEqual(wire,"idle" if state=="idle"
                                         else "quiet-"+state)
                        self.assertEqual(description,"Prueba")

    def test_windhawk_cpp_never_autoexpands_from_voice_message(self):
        source=Path(__file__).resolve().parents[2] / (
            "HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp")
        code=source.read_text(encoding="utf-8")
        section=code.split("void ReadVoiceBridge() {",1)[1].split(
            "\nvoid ReadBridgeState()",1)[0]
        self.assertIn("g_voiceExpandUntil=0;",section)
        self.assertIn("g_voiceNoticeUntil=0;",section)
        self.assertNotIn("ChangePage(page)",section)


class ExplorerWindowTests(unittest.TestCase):
    def test_close_explorer_when_powershell_is_in_front(self):
        gui,con=windows_mock()
        with patch.dict(sys.modules,{"win32gui":gui,"win32con":con}):
            msg=pc_files.close_foreground_window("explorer")
        self.assertIn("Descargas",msg)
        gui.PostMessage.assert_called_once_with(20,16,0,0)
        gui.PostMessage.assert_not_called_with(10,16,0,0)

    def test_close_downloads_selects_correct_window_even_with_two_explorers(self):
        gui,con=windows_mock()
        pythoncom=MagicMock()
        shellclient=MagicMock()
        shell=MagicMock()
        window1=MagicMock(HWND=30)
        window1.Document.Folder.Self.Path=r"C:\Users\Test\Documents"
        window2=MagicMock(HWND=20)
        window2.Document.Folder.Self.Path=r"C:\Users\Test\Downloads"
        shell.Windows.return_value=[window1,window2]
        shellclient.Dispatch.return_value=shell
        win32com=MagicMock(client=shellclient)
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"Downloads"
            folder.mkdir()
            window2.Document.Folder.Self.Path=str(folder.resolve())
            with patch.dict(sys.modules,{
                    "win32gui":gui,"win32con":con,
                    "pythoncom":pythoncom,
                    "win32com":win32com,
                    "win32com.client":shellclient}), \
                 patch("hover_next.pc_files._known_folder",
                       return_value=folder.resolve()):
                pc_files.close_foreground_window("downloads")
        gui.PostMessage.assert_called_once_with(20,16,0,0)
        pythoncom.CoInitialize.assert_called_once()
        pythoncom.CoUninitialize.assert_called_once()

    def test_refuses_to_close_unrelated_window(self):
        gui,con=windows_mock()
        with patch.dict(sys.modules,{"win32gui":gui,"win32con":con}):
            with self.assertRaises(pc_files.PCFileError):
                pc_files.close_foreground_window("word")
        gui.PostMessage.assert_not_called()

    def test_voice_recognizes_downloads_and_explorer(self):
        cases=(
            ("Oye Hover, cierra descargas","downloads"),
            ("Hover, cierra la carpeta de descargas","downloads"),
            ("Oye Hover, cierra el explorador de archivos","explorer"),
            ("Hover, cierra documentos","documents"),
        )
        for spoken,target in cases:
            with self.subTest(spoken=spoken):
                intent=parse(spoken)
                self.assertEqual(intent.action,"pc_close_window")
                self.assertEqual(intent.args,{"app":target})
                self.assertFalse(intent.requires_confirmation)


if __name__=="__main__":
    unittest.main()

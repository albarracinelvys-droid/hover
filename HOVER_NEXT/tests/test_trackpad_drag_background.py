"""Trackpad/eye-grip C++ regressions and detached Windows startup tests."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from hover_next import launch_background


class WindhawkGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[2]/
                    "HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp").read_text(
                        encoding="utf-8")

    def test_touchpad_and_mouse_wheel_navigate_over_island(self):
        code=self.source
        for token in ("WM_MOUSEWHEEL","WM_MOUSEHWHEEL",
                      "WM_POINTERWHEEL","WM_POINTERHWHEEL",
                      "LowLevelWheelHook","kWheelMessage","WM_GESTURE",
                      "HandleSwipeDelta","ChangePage(g_currentPage+direction)"):
            with self.subTest(token=token):
                self.assertIn(token,code)
        self.assertIn("g_open<0.35f",code)
        self.assertIn("g_eyeGripDrag",code)

    def test_between_eye_grip_physically_moves_island_not_pages(self):
        code=self.source
        self.assertIn("const float centerX=float(r.right-r.left)*0.5f;",code)
        self.assertIn("std::abs(localX-centerX)<=16.0f",code)
        self.assertIn("g_islandShiftX=g_grabStartShiftX+dx;",code)
        self.assertIn("g_islandShiftY=g_grabStartShiftY+dy;",code)
        self.assertIn("g_eyeGripDrag=false;",code)
        self.assertIn("if(releasedGrip){",code)
        self.assertIn("const int baseX=",code)
        self.assertIn("const int baseY=",code)
        self.assertIn("std::max(screen.left,screen.right-w)",code)

    def test_larger_eye_animation(self):
        self.assertIn("const float scale=1.0f+0.75f*smooth;",self.source)
        self.assertIn("g.TranslateTransform(cx,anchorY);",self.source)
        self.assertIn("const float smooth=opening*opening*(3.0f-2.0f*opening);",
                      self.source)


class DetachedLaunchTests(unittest.TestCase):
    def test_start_uses_pythonw_detached_and_logs_outside_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            py=work/"python.exe"
            pythonw=work/"pythonw.exe"
            pythonw.touch()
            pid_file=work/"voice.pid"
            log_file=work/"voice.log"
            process=MagicMock(pid=31204)
            process.poll.return_value=None
            with patch("hover_next.launch_background.sys.platform","win32"), \
                 patch("hover_next.launch_background.sys.executable",str(py)), \
                 patch("hover_next.launch_background.current_pid",return_value=None), \
                 patch("hover_next.launch_background.state_paths",
                       return_value=(pid_file,log_file)), \
                 patch("hover_next.launch_background.subprocess.Popen",
                       return_value=process) as popen, \
                 patch("hover_next.launch_background.time.sleep"):
                self.assertEqual(launch_background.start(),0)
            args=popen.call_args.args[0]
            self.assertEqual(args[0],str(pythonw))
            self.assertEqual(args[1:3],["-m","hover_next.app"])
            self.assertIn("--voice",args)
            kwargs=popen.call_args.kwargs
            self.assertIs(kwargs["stdin"],launch_background.subprocess.DEVNULL)
            self.assertIs(kwargs["stderr"],launch_background.subprocess.STDOUT)
            self.assertTrue(kwargs["creationflags"] & 0x00000008)
            self.assertEqual(pid_file.read_text(encoding="ascii"),"31204")
            self.assertIn("Iniciando HOVER",log_file.read_text(encoding="utf-8"))

    def test_existing_voice_engine_is_not_started_again(self):
        with patch("hover_next.launch_background.sys.platform","win32"), \
             patch("hover_next.launch_background.current_pid",return_value=3456), \
             patch("hover_next.launch_background.subprocess.Popen") as popen:
            self.assertEqual(launch_background.start(),0)
        popen.assert_not_called()

    def test_stop_only_targets_verified_voice_pid(self):
        with tempfile.TemporaryDirectory() as d:
            pid_file=Path(d)/"voice.pid"
            pid_file.write_text("31415")
            process=MagicMock()
            psutil=MagicMock()
            psutil.Process.return_value=process
            with patch("hover_next.launch_background.current_pid",
                       return_value=31415), \
                 patch("hover_next.launch_background.state_paths",
                       return_value=(pid_file,Path(d)/"voice.log")), \
                 patch.dict("sys.modules",{"psutil":psutil}):
                self.assertEqual(launch_background.stop(),0)
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)
            self.assertFalse(pid_file.exists())

    def test_stop_without_running_engine_does_not_kill_python(self):
        with patch("hover_next.launch_background.current_pid",return_value=None), \
             patch("hover_next.launch_background.subprocess.run") as cmd:
            self.assertEqual(launch_background.stop(),0)
        cmd.assert_not_called()

    def test_all_launchers_keep_console_opt_in(self):
        root=Path(__file__).resolve().parents[1]
        silent=(root/"INICIAR_VOZ.bat").read_text()
        interactive=(root/"INICIAR_VOZ_CONSOLA.bat").read_text()
        self.assertIn("hover_next.launch_background",silent)
        self.assertNotIn("pause",silent.lower())
        self.assertIn("hover_next.app --voice",interactive)
        self.assertIn("pause",interactive.lower())
        self.assertIn("hover_next.launch_background --stop",
                      (root/"DETENER_HOVER.bat").read_text())


if __name__=="__main__":
    unittest.main()

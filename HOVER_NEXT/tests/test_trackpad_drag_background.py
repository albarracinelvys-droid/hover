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
        self.assertIn("bool IsEyeGripScreenPoint(HWND hwnd,const POINT& point)",code)
        self.assertIn("std::abs(point.x-middle)<=23",code)
        self.assertIn("const int middle=(bounds.left+bounds.right)/2;",code)
        self.assertIn("g_islandShiftX=g_grabStartShiftX+dx;",code)
        self.assertIn("g_islandShiftY=g_grabStartShiftY+dy;",code)
        self.assertIn("g_eyeGripDrag=false;",code)
        self.assertIn("void FinishEyeGrip(HWND hwnd)",code)
        self.assertIn("case kEyeGripEnd:",code)
        self.assertIn("const int baseX=",code)
        self.assertIn("const int baseY=",code)
        self.assertIn("std::max(screen.left,screen.right-w)",code)
        self.assertIn("void SaveIslandPosition()",code)
        self.assertIn("void LoadIslandPosition()",code)
        self.assertIn("posicion_isla.txt",code)
        self.assertIn("if(moved)SaveIslandPosition();",code)

    def test_low_level_click_interception_works_when_layered_window_misses_click(self):
        code=self.source
        hook=code.split("LRESULT CALLBACK LowLevelWheelHook",1)[1].split(
            "LRESULT CALLBACK HoverKeyboardHook",1)[0]
        self.assertIn("wp==WM_LBUTTONDOWN",hook)
        self.assertIn("wp==WM_LBUTTONUP",hook)
        self.assertIn("IsEyeGripScreenPoint(hwnd,e->pt)",hook)
        self.assertIn("PostMessageW(hwnd,kEyeGripBegin,0,0)",hook)
        self.assertIn("PostMessageW(hwnd,kEyeGripEnd,0,0)",hook)
        self.assertIn("g_hookGripActive.exchange(false)",hook)
        self.assertIn("if(!(e->flags & LLMHF_INJECTED))",hook)
        self.assertIn("return CallNextHookEx(nullptr,code,wp,lp);",hook)
        # The hook must not swallow arbitrary clicks outside the tiny grip.
        self.assertIn("std::abs(point.x-middle)<=23",code)
        self.assertIn("point.y>=bounds.top+2",code)
        self.assertIn("point.y<=bounds.top+44",code)

    def test_grip_mouse_up_commits_position_without_swiping_pages(self):
        code=self.source
        block=code.split("case WM_LBUTTONUP:",1)[1].split(
            "case WM_CAPTURECHANGED:",1)[0]
        self.assertIn("if(g_eyeGripDrag)",block)
        self.assertIn("FinishEyeGrip(hwnd);",block)
        self.assertIn("return 0;",block)
        self.assertIn("ChangePage(",block)
        begin=code.split("case kEyeGripBegin:",1)[1].split(
            "case kArrowNavigation:",1)[0]
        self.assertIn("BeginEyeGrip(hwnd,pointer);",begin)
        self.assertIn("FinishEyeGrip(hwnd);",begin)

    def test_eyes_are_closer_without_disabling_large_eye_animation(self):
        self.assertIn("const float eyeCenter=cx+(i==0?-14.2f:14.2f);",
                      self.source)
        self.assertNotIn("?-16.4f:16.4f",self.source)
        self.assertIn("const float scale=1.0f+0.75f*smooth;",
                      self.source)

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

    def test_realtek_launcher_keeps_original_device_and_threshold(self):
        root=Path(__file__).resolve().parents[1]
        content=(root/"INICIAR_SILENCIOSO_REALTEK.bat").read_text()
        self.assertIn("--mic 9 --threshold 0.0006",content)
        self.assertIn("hover_next.launch_background",content)

    def test_background_launch_preserves_motor_args(self):
        # The launcher restricts options to known engine/mic/threshold flags.
        with patch("hover_next.launch_background.start",return_value=0) as launch, \
             patch("hover_next.launch_background.sys.argv",
                   ["launcher","--engine","whisper","--mic","9",
                    "--threshold","0.0006"]):
            self.assertEqual(launch_background.main(),0)
        launch.assert_called_once_with(engine="whisper",mic=9,threshold=0.0006,model="base")

    def test_explicit_accuracy_profile_reaches_background_launcher(self):
        with patch("hover_next.launch_background.start",return_value=0) as launch, \
             patch("hover_next.launch_background.sys.argv",
                   ["launcher","--engine","whisper","--model","small"]):
            self.assertEqual(launch_background.main(),0)
        launch.assert_called_once_with(engine="whisper",mic=None,
                                       threshold=None,model="small")

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

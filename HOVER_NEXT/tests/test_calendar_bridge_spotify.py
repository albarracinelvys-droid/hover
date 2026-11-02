"""Calendar island and Spotify session regression tests (no live credentials)."""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from hover_next import calendar_bridge as cb
from hover_next import desktop,google_workspace
from hover_next.intent import parse


class CalendarBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"calendar_events.tsv"
        mock=patch("hover_next.calendar_bridge._bridge_path",
                   return_value=self.path)
        mock.start()
        self.addCleanup(mock.stop)

    def test_reads_real_google_events_and_validates_links(self):
        api=MagicMock()
        api.events().list().execute.return_value={
            "items":[
                {"summary":"Reunión materia nula",
                 "start":{"date":"2026-11-01"},
                 "htmlLink":"https://calendar.google.com/calendar/event?eid=abc"},
                {"summary":"Evento con enlace no confiable",
                 "start":{"dateTime":"2026-11-02T10:00:00-05:00"},
                 "htmlLink":"https://calendar.google.com.evil.invalid/collect"},
            ]}
        with patch("hover_next.google_workspace._service",return_value=api):
            got=cb.read_calendar_events(
                datetime(2026,10,31,tzinfo=timezone.utc))
        self.assertEqual(got[0][0],"2026-11-01")
        self.assertEqual(got[0][1],"Reunión materia nula")
        self.assertTrue(got[0][2].startswith("https://calendar.google.com/"))
        self.assertEqual(got[1][2],"")
        kwargs=api.events().list.call_args.kwargs
        self.assertEqual(kwargs["calendarId"],"primary")
        self.assertTrue(kwargs["singleEvents"])
        self.assertIn("summary",kwargs["fields"])
        self.assertNotIn("attendees",kwargs["fields"])
        self.assertNotIn("description",kwargs["fields"])

    def test_atomic_snapshot_contains_events_but_no_private_credentials(self):
        cb.write_snapshot([
            ("2026-11-01","Reunión materia nula",
             "https://calendar.google.com/calendar/event?eid=abc"),
            ("2026-11-02","Evento\nconfidencial\t",
             "https://example.com/tracker"),
        ])
        data=self.path.read_text(encoding="utf-8")
        self.assertTrue(data.startswith("status\tok\n"))
        self.assertIn("2026-11-01\tReunión materia nula\t",data)
        self.assertIn("2026-11-02\tEvento confidencial\t\n",data)
        self.assertNotIn("access_token",data)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_invalid_credentials_does_not_surface_old_cached_events(self):
        from hover_next.google_auth import GoogleAuthError
        cb.write_snapshot([("2026-11-01","Old event","")])
        with patch("hover_next.google_auth.credentials",
                   side_effect=GoogleAuthError("expired secret")):
            self.assertFalse(cb.refresh())
        self.assertEqual(self.path.read_text(encoding="utf-8"),
                         "status\tdisconnected\n")

    def test_refresh_after_calendar_creation_is_async(self):
        api=MagicMock()
        api.events().insert().execute.return_value={"id":"valid-event"}
        with patch("hover_next.google_workspace._service",return_value=api), \
             patch("hover_next.calendar_bridge.request_refresh") as update:
            message=google_workspace.calendar_create_event(
                "Reunión","mañana",now=datetime(2026,10,31,9,0,
                                               tzinfo=__import__("zoneinfo").ZoneInfo(
                                                   "America/Bogota")))
        self.assertIn("Reunión",message)
        update.assert_called_once()

    def test_windhawk_cpp_shows_clickable_events_without_auto_expansion(self):
        source=Path(__file__).resolve().parents[2]/(
            "HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp")
        content=source.read_text(encoding="utf-8")
        self.assertIn('ReadSmallFile(L"calendar_events.tsv"',content)
        self.assertIn("DayEvents(year,month,day)",content)
        self.assertIn("g_calendarDetailsOpen=true",content)
        self.assertIn("if(action==650)",content)
        self.assertIn('https://calendar.google.com/',content)
        self.assertIn("g_voiceExpandUntil=0",content)


class SpotifyPlaybackTests(unittest.TestCase):
    def test_open_spotify_does_not_toggle_play_pause(self):
        self.assertEqual(parse("Hover abre Spotify").action,"spotify_open")
        self.assertEqual(parse("Hover reproduce Spotify").action,"spotify_play")
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop.os.startfile",create=True) as launch, \
             patch("hover_next.desktop._spotify_session_play") as play:
            result=desktop.spotify_start_playback(open_app=True,play=False)
        launch.assert_called_once_with("spotify:")
        play.assert_not_called()
        self.assertIn("Spotify abierto",result)

    def test_reproduce_without_session_does_not_claim_audio_or_toggle_other_apps(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._spotify_session_play",
                   return_value="no_session"), \
             patch("time.sleep") as sleep, \
             patch("hover_next.desktop.send_media_key") as toggle, \
             patch("hover_next.desktop.os.startfile",create=True):
            message=desktop.spotify_start_playback(open_app=True,play=True)
        self.assertIn("no detectó una sesión",message)
        toggle.assert_not_called()
        self.assertEqual(sleep.call_count,7)

    def test_windows_confirmed_playback_is_reported(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._spotify_session_play",
                   return_value="playing"):
            result=desktop.spotify_start_playback(open_app=False)
        self.assertIn("confirma una sesión",result)

    def test_api_unavailable_requires_install_not_media_toggle(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._spotify_session_play",
                   return_value="missing_api"), \
             patch("hover_next.desktop.send_media_key") as toggle:
            message=desktop.spotify_start_playback(open_app=False)
        self.assertIn("requirements.txt",message)
        toggle.assert_not_called()


if __name__=="__main__":
    unittest.main()

"""Real HOVER media-bridge regression tests without Windows, Spotify or audio."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock,MagicMock,patch

from hover_next import media_bridge,desktop


class AutoBridgeTests(unittest.TestCase):
    def test_spotify_session_has_priority_over_unrelated_chrome(self):
        chrome=MagicMock(source_app_user_model_id="Google.Chrome")
        spotify=MagicMock(source_app_user_model_id="Spotify.exe")
        manager=MagicMock()
        manager.get_sessions.return_value=[chrome,spotify]
        manager.get_current_session.return_value=chrome
        session,is_spotify=media_bridge.choose_session(manager)
        self.assertIs(session,spotify)
        self.assertTrue(is_spotify)

    def test_falls_back_to_another_media_session_when_spotify_absent(self):
        other=MagicMock(source_app_user_model_id="Microsoft.ZuneMusic")
        manager=MagicMock()
        manager.get_sessions.return_value=[other]
        manager.get_current_session.return_value=other
        session,is_spotify=media_bridge.choose_session(manager)
        self.assertIs(session,other)
        self.assertFalse(is_spotify)

    def test_media_buttons_play_pause_are_specific_to_selected_session(self):
        selected=MagicMock()
        selected.try_play_async=AsyncMock(return_value=True)
        selected.try_pause_async=AsyncMock(return_value=True)
        selected.try_skip_next_async=AsyncMock(return_value=True)
        selected.try_skip_previous_async=AsyncMock(return_value=True)
        playback=MagicMock()
        with patch("hover_next.media_bridge.PlaybackStatus") as statuses:
            playback.playback_status=statuses.PAUSED
            selected.get_playback_info.return_value=playback
            asyncio.run(media_bridge.apply_command(selected,"play"))
            selected.try_play_async.assert_awaited_once()
            selected.try_pause_async.assert_not_awaited()
            playback.playback_status=statuses.PLAYING
            asyncio.run(media_bridge.apply_command(selected,"play"))
            selected.try_pause_async.assert_awaited_once()
            asyncio.run(media_bridge.apply_command(selected,"next"))
            asyncio.run(media_bridge.apply_command(selected,"prev"))
        selected.try_skip_next_async.assert_awaited_once()
        selected.try_skip_previous_async.assert_awaited_once()

    def test_album_cover_reads_awaited_stream_and_persists_hashed_png(self):
        png=b"\\x89PNG\\r\\n\\x1a\\n"+b"a"*150
        # The source uses bytes literals; a fake WinRT IBuffer acts as bytes.
        png=bytes([137,80,78,71,13,10,26,10])+b"Z"*100
        ref=MagicMock()
        stream=MagicMock(size=len(png))
        stream.get_input_stream_at.return_value=stream
        stream.read_async=AsyncMock(return_value=memoryview(png))
        ref.open_read_async=AsyncMock(return_value=stream)
        media=MagicMock(thumbnail=ref)
        with tempfile.TemporaryDirectory() as td, \
             patch("hover_next.media_bridge.BASE",Path(td)), \
             patch("hover_next.media_bridge.InputStreamOptions") as options:
            result=asyncio.run(media_bridge.cover_from_media(media))
            self.assertTrue(result.startswith("cover_"))
            self.assertTrue(result.endswith(".png"))
            self.assertEqual((Path(td)/result).read_bytes(),png)
            options.NONE.assert_not_called()
        ref.open_read_async.assert_awaited_once()
        stream.read_async.assert_awaited_once()

    def test_bridge_format_has_spotify_metadata_and_cover_filename(self):
        with tempfile.TemporaryDirectory() as td, \
             patch("hover_next.media_bridge.BASE",Path(td)), \
             patch("hover_next.media_bridge.STATUS",Path(td)/"status.txt"):
            media_bridge.write_state({
                "spotify":1,"playing":1,"title":"Reunión","artist":"Artista",
                "artwork":"cover_0123456789abcdef.jpg",
                "progress":"0.38"})
            state=(Path(td)/"status.txt").read_text(encoding="utf-8")
        self.assertIn("spotify=1",state)
        self.assertIn("title=Reunión",state)
        self.assertIn("artwork=cover_0123456789abcdef.jpg",state)
        self.assertIn("playing=1",state)

    def test_hovers_launch_start_music_automatically(self):
        source=Path(__file__).resolve().parents[1]/"hover_next"/"voice_coucou.py"
        body=source.read_text(encoding="utf-8")
        self.assertIn("start_media_bridge(stop)",body)

    def test_windhawk_uses_bridge_button_commands_and_animated_feedback(self):
        code=(Path(__file__).resolve().parents[2]/
              "HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp").read_text(
                  encoding="utf-8")
        self.assertIn('WriteBridgeCommand("play")',code)
        self.assertIn('WriteBridgeCommand("next")',code)
        self.assertIn('WriteBridgeCommand("prev")',code)
        self.assertIn("float radius=20.0f+15.0f*t;",code)
        self.assertIn("g_feedbackUntil=GetTickCount64()+650;",code)
        self.assertIn("RefreshCoverIfNeeded(m.artwork)",code)

    def test_reproduce_existing_spotify_never_relaunches_application(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._spotify_session_play",
                   return_value="playing"), \
             patch("hover_next.desktop.os.startfile",create=True) as start:
            message=desktop.spotify_start_playback(open_app=True,play=True)
        self.assertIn("confirma una sesión",message)
        start.assert_not_called()

    def test_play_request_is_truthful_if_winrt_does_not_confirm(self):
        with patch("hover_next.desktop.sys.platform","win32"), \
             patch("hover_next.desktop._spotify_session_play",
                   return_value="requested"), \
             patch("hover_next.desktop.os.startfile",create=True) as start:
            message=desktop.spotify_start_playback(open_app=True,play=True)
        self.assertIn("todavía no confirmó",message)
        start.assert_not_called()


if __name__=="__main__":
    unittest.main()

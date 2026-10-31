"""Pruebas de rutas y acciones simuladas: NO prueban micrófono ni navegador real."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

SOURCE = Path(__file__).with_name("Asistente_Voz_HOVER_v4_3.py")
spec = importlib.util.spec_from_file_location("hover_voice_v43", SOURCE)
h = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(h)

class Voice43(unittest.TestCase):
    def test_whisper_spotify_typo(self):
        self.assertEqual(h.canonical_command('Reproces Spotify.'),'reproduce spotify')
        with patch.object(h,'open_spotify',return_value=True) as opened, \
             patch.object(h,'play_spotify_targeted',return_value='started') as direct:
            result,page=h.process_command('Reproces Spotify.')
            self.assertIn('Spotify',result)
            self.assertEqual(page,0)
            opened.assert_called_once()
            direct.assert_called_once()

    def test_chatgpt_browser_launch(self):
        with patch.object(h.webbrowser,'open',return_value=True) as launch:
            result,page=h.process_command('abre ChatGPT')
        self.assertIn('chatgpt',result.lower())
        self.assertEqual(page,3)
        launch.assert_called_once_with('https://chatgpt.com/',new=2)

    def test_browser_failure_is_not_false_success(self):
        with patch.object(h.webbrowser,'open',return_value=False):
            result,_=h.process_command('abre ChatGPT')
            self.assertIn('No pude',result)

    def test_close_chatgpt_only_verified(self):
        with patch.object(h,'close_foreground_chatgpt_tab',return_value='Solicité cerrar la pestaña activa de ChatGPT.') as closing:
            result,_=h.process_command('cierra la última pestaña de ChatGPT')
        closing.assert_called_once()
        self.assertIn('ChatGPT',result)
        result,_=h.process_command('cierra la ventana de Excel')
        self.assertIn('No cerré nada',result)

    def test_wake_then_command(self):
        events=[]
        with patch.object(h,'notify',side_effect=lambda state,message,page=-1: events.append((state,message,page))), \
             patch.object(h,'close_foreground_chatgpt_tab',return_value='No cerré nada: activa la pestaña de ChatGPT.'):
            handled,awaiting=h.process_utterance('Oye Hover.',False)
            self.assertTrue(handled)
            self.assertTrue(awaiting)
            handled,awaiting=h.process_utterance('Cierra la última pestaña de ChatGPT.',awaiting)
            self.assertTrue(handled)
        self.assertEqual(events[-1][0],'error')
        self.assertIn('No cerré nada',events[-1][1])

    def test_wake_and_spotify_one_phrase(self):
        with patch.object(h,'open_spotify',return_value=True), \
             patch.object(h,'play_spotify_targeted',return_value='already_playing'), \
             patch.object(h,'notify') as notify:
            handled,_=h.process_utterance('Oye Hover. Reproces Spotify.',False)
            self.assertTrue(handled)
            self.assertIn('Spotify ya está reproduciendo',notify.call_args[0][1])

    def test_no_background_activation(self):
        self.assertIsNone(h.WAKE.match(h.norm('esta es una clase sobre cluster oye hover abre chatgpt')))

    def test_spoken_capture(self):
        with patch.object(h,'capture_screen',return_value='Selecciona la región.') as capture:
            result,_=h.process_command('toma una captura de pantalla')
        self.assertEqual(result,'Selecciona la región.')
        capture.assert_called_once()

    def test_move_requires_confirmation(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            downloads=root/'Downloads';downloads.mkdir()
            destination=root/'Favorita';destination.mkdir()
            item=downloads/'reporte.xlsx';item.write_bytes(b'abc')
            with patch.object(h,'downloads_folder',return_value=downloads), \
                 patch.object(h,'favorite_folder',return_value=destination):
                result,_=h.process_command('mueve el ultimo archivo de descargas a la carpeta configurada')
                self.assertIn('Confirmas mover',result)
                self.assertTrue(item.exists())
                result,_=h.process_command('confirmar')
                self.assertIn('movido',result)
                self.assertTrue((destination/item.name).exists())

if __name__=='__main__':
    unittest.main(verbosity=2)

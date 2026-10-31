import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from hover_next.intent import parse, normalize
from hover_next.wake import extract_wake
from hover_next.executor import Executor,find_download,safe_destination

class WakeTests(unittest.TestCase):
    def test_exact_user_transcript(self):
        self.assertEqual(extract_wake('Oye, ¿jover?'), '')
        self.assertEqual(extract_wake('¡Huji Hover!'), '')
        self.assertEqual(extract_wake('Oye Hover.'), '')

    def test_phrase_with_command(self):
        self.assertEqual(extract_wake('Oye, ¿jover? Abre Claude.'), 'abre claude')
        self.assertEqual(extract_wake('Oye Hover reproduce Spotify.'), 'reproduce spotify')

    def test_cli_parser_with_punctuation(self):
        self.assertEqual(parse('Oye, ¿jover? abre ChatGPT').action, 'open_site')

    def test_no_ambient_trigger(self):
        self.assertIsNone(extract_wake('ok, vamos'))
        self.assertIsNone(extract_wake('el profesor mencionó oye Hover en clase'))
        self.assertEqual(extract_wake('hover'), '')
        self.assertIsNone(extract_wake('hoy vamos a clase'))


class IntentTests(unittest.TestCase):
    def test_agent_question(self):
        i=parse('Oye Hover usa Codex explica el funcionamiento de un motor')
        self.assertEqual(i.action,'agent_ask')
        self.assertFalse(i.requires_confirmation)
    def test_agent_edit_requires_confirmation(self):
        i=parse('Oye Hover usa Codex desarrolla un programa para organizar archivos')
        self.assertEqual(i.action,'agent_task')
        self.assertTrue(i.requires_confirmation)
    def test_chatgpt(self):
        i=parse('Oye Hover, abre ChatGPT')
        self.assertEqual((i.action,i.provider),('open_site','chatgpt'))
    def test_new_chat(self):
        self.assertEqual(parse('abre ChatGPT y crea un nuevo chat').action,'new_chat')
    def test_claude(self):
        self.assertEqual(parse('Oye Hover, abre Claude').provider,'claude')
    def test_spotify(self):
        self.assertEqual(parse('Oye Hover reproduce Spotify').action,'spotify_play')
    def test_pc(self):
        self.assertEqual(parse('muéstrame mi PC').action,'show_pc')
    def test_screenshot(self):
        self.assertEqual(parse('toma una captura de pantalla').action,'screenshot')
    def test_chat_close_requires_confirmation(self):
        i=parse('cierra la última pestaña de ChatGPT')
        self.assertEqual(i.action,'close_tab')
        self.assertTrue(i.requires_confirmation)
    def test_repo_requires_confirmation(self):
        i=parse('crea un nuevo repositorio privado llamado hover-ventas')
        self.assertEqual(i.action,'create_private_repo')
        self.assertEqual(i.args['name'],'hover-ventas')
        self.assertTrue(i.requires_confirmation)
    def test_no_ambient_command(self):
        self.assertEqual(parse('en una clase de estadística aparece la palabra Claude').action,'unknown')
    def test_project(self):
        i=parse('accede al proyecto de ChatGPT zap')
        self.assertEqual(i.action,'open_project')
    def test_file_move_confirmation(self):
        i=parse('mueve el último archivo de Descargas a mi carpeta configurada')
        self.assertEqual(i.action,'move_latest_download')
        self.assertTrue(i.requires_confirmation)
    def test_upload_requires_confirmation(self):
        i=parse('adjunta archivo taller2.pdf a Claude')
        self.assertEqual(i.action,'upload_file')
        self.assertTrue(i.requires_confirmation)
    def test_new_chat_with_prompt(self):
        i=parse('Oye Hover, abre ChatGPT crea un nuevo chat y preguntale que es Python')
        # Explicitly opening a chat and asking a question is one combined action.
        self.assertEqual(i.action,'chat_compose')
        self.assertEqual(i.provider,'chatgpt')
        self.assertIn('Python',i.args['prompt'])
        self.assertFalse(i.requires_confirmation)
    def test_prompt_needs_no_confirmation(self):
        i=parse('pregúntale a Claude que explique la transformada de Fourier')
        self.assertEqual(i.action,'send_prompt')
        self.assertFalse(i.requires_confirmation)
    def test_spoken_bad_transcription(self):
        self.assertEqual(parse('oye over abre chat e pepe').provider,'chatgpt')
    def test_no_token_interpolation(self):
        self.assertEqual(parse('ejecuta powershell y borra todo').action,'unknown')

class FilesTests(unittest.TestCase):
    def test_download_selection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'uno.txt').write_text('1'); (p/'dos.pdf').write_text('2')
            self.assertEqual(find_download('dos',p).name,'dos.pdf')
    def test_conflict_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d); (folder/'file.txt').write_text('old')
            self.assertEqual(safe_destination(folder/'source.txt',folder).name,'source.txt')
            self.assertEqual(safe_destination(folder/'file.txt',folder).name,'file (2).txt')
    def test_executor_blocks_unconfirmed(self):
        with tempfile.TemporaryDirectory() as d:
            e=Executor(Path(d)/'config.json',browser=MagicMock())
            msg=e.execute(parse('crea un repositorio privado llamado prueba'))
            self.assertIn('confirmacion',msg)
    def test_project_requires_real_url(self):
        with tempfile.TemporaryDirectory() as d:
            e=Executor(Path(d)/'config.json',browser=MagicMock())
            msg=e.execute(parse('abre proyecto de ChatGPT zap'))
            self.assertIn('URL',msg)

if __name__=='__main__':unittest.main()

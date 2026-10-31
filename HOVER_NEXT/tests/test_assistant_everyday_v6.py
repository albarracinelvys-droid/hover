"""User-recorded Spanish phrases, app routing, safety and execution mocks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hover_next.intent import parse
from hover_next.executor import Executor, confirm_intent
from hover_next.voice_coucou import VoiceDialogue
from hover_next.desktop import ActionUnavailable

class RecordedVoiceCommands(unittest.TestCase):
    def test_actual_repo_request_from_log(self):
        phrase = 'Hover, crea un nuevo repositorio privado en github que se llama Materialula.'
        i = parse(phrase)
        self.assertEqual(i.action,'create_private_repo')
        self.assertEqual(i.args['name'],'materialula')
        self.assertTrue(i.requires_confirmation)

    def test_private_repo_variants(self):
        cases = [
            'crea un repositorio privado en github llamado materia-nula',
            'crea un repositorio en github privado llamado materia-nula',
            'crea un nuevo repo privado que se llama materia-nula',
            'crea un repo privado con el nombre de materia-nula',
            'crea un repositorio privado en github que se llame materia-nula',
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                i=parse('Hover '+phrase)
                self.assertEqual(i.action,'create_private_repo')
                self.assertEqual(i.args['name'],'materia-nula')
                self.assertTrue(i.requires_confirmation)

    def test_incomplete_private_repo_command_does_not_create(self):
        self.assertEqual(parse('Hover crea un repositorio privado en GitHub').action,'repo_name_needed')
        self.assertNotEqual(parse('Hover crea un repositorio publico en GitHub llamado demo').action,
                            'create_private_repo')

    def test_voice_mishearing_after_wake(self):
        i = parse('Hover. Oye Calculadora.')
        self.assertEqual(i.action,'windows_app')
        self.assertEqual(i.args['app'],'calculator')

    def test_improved_local_apps(self):
        mapping={
            'Hover abre calculadora': ('windows_app','calculator'),
            'Hover abre el bloc de notas': ('windows_app','notepad'),
            'Hover abre el administrador de tareas': ('windows_app','task_manager'),
            'Hover abre el explorador de Windows': ('windows_app','explorer'),
            'Hover abre la carpeta descargas': ('windows_app','downloads'),
            'Hover abre la terminal': ('windows_app','terminal'),
            'Hover abre configuracion de Windows': ('windows_app','settings'),
        }
        for phrase,(action,app) in mapping.items():
            with self.subTest(phrase=phrase):
                i=parse(phrase)
                self.assertEqual(i.action,action)
                self.assertEqual(i.args['app'],app)

    def test_web_shortcuts_from_voice(self):
        for app in ('GitHub','WhatsApp','Outlook','OneDrive','Discord',
                    'LinkedIn','Canva','Notion','Gemini','Vercel'):
            with self.subTest(app=app):
                i=parse('Hover abre '+app)
                self.assertEqual(i.action,'open_link')

    def test_google_docs_stays_google_docs(self):
        self.assertEqual(parse('Hover crea un documento de Google').args['service'],
                         'google_docs_new')
        self.assertEqual(parse('Hover abre una nueva pestaña de Google').args['service'],
                         'google_home')

    def test_media_and_volume_commands(self):
        cases={
            'Hover pausa la música':'play_pause',
            'Hover siguiente canción':'next',
            'Hover canción anterior':'previous',
            'Hover sube el volumen':'volume_up',
            'Hover baja el volumen':'volume_down',
            'Hover silencia':'volume_mute',
        }
        for utterance,key in cases.items():
            with self.subTest(utterance=utterance):
                i=parse(utterance)
                self.assertEqual(i.action,'media_key')
                self.assertEqual(i.args['key'],key)

    def test_help_command(self):
        self.assertEqual(parse('Hover que puedes hacer').action,'show_help')

    def test_unrecognized_creative_instruction_never_runs_software(self):
        self.assertEqual(parse('Hover crea uno rapo en guitarra').action,'unknown')

class Safeguards(unittest.TestCase):
    def test_repo_name_confirmation_wrong_name_fails(self):
        i=parse('Hover crea repo privado llamado materialula')
        with patch('builtins.input',return_value='materianula'):
            self.assertFalse(confirm_intent(i))

    def test_repo_name_confirmation_right_name_succeeds(self):
        i=parse('Hover crea repo privado llamado materialula')
        with patch('builtins.input',return_value='materialula'):
            self.assertTrue(confirm_intent(i))

    def test_repo_exec_uses_only_gh_private(self):
        i=parse('Hover crea un repositorio privado en Github llamado hover-proyecto')
        with tempfile.TemporaryDirectory() as tmp:
            e=Executor(config_path=Path(tmp)/'config.json',browser=MagicMock())
            mock_process=MagicMock(returncode=0,stdout='https://github.com/account/hover-proyecto',stderr='')
            with patch('hover_next.executor.shutil.which',return_value='gh.exe'), \
                 patch('hover_next.executor.subprocess.run',return_value=mock_process) as runner:
                e.execute(i,confirmed=True)
            cmd=runner.call_args.args[0]
            self.assertEqual(cmd[:4],['gh.exe','repo','create','hover-proyecto'])
            self.assertIn('--private',cmd)
            self.assertNotIn('--public',cmd)
            self.assertFalse(runner.call_args.kwargs.get('shell',False))

    def test_unsupported_url_not_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Executor(config_path=Path(tmp)/'config.json',browser=MagicMock())
            from hover_next.intent import Intent
            with self.assertRaises(ActionUnavailable):
                e.execute(Intent('open_link',args={'site':'https://evil.example'}))

    def test_real_github_open_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Executor(config_path=Path(tmp)/'config.json',browser=MagicMock())
            with patch('hover_next.desktop.webbrowser.open_new_tab',return_value=True) as opener:
                result=e.execute(parse('Hover abre GitHub'))
            self.assertIn('github',result.lower())
            opener.assert_called_once_with('https://github.com/')

    def test_voice_wake_mishearing_executes(self):
        results=[]
        dialogue=VoiceDialogue(lambda command: results.append(parse(command)) or 'ok',
                               lambda provider,msg:None,
                               clock=lambda:300.0)
        with patch('hover_next.voice_coucou.publish'):
            status=dialogue.process('Hover. Oye Calculadora.')
        self.assertEqual(status,'action')
        self.assertEqual(results[0].action,'windows_app')

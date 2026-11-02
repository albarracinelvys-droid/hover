"""Explain why speech is unknown without running user actions or needing Ollama."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock,patch

from hover_next import diagnostics,local_nlu


class NLUSemanticsTests(unittest.TestCase):
    def setUp(self):
        local_nlu._CACHE.clear()
        local_nlu._MISSING_UNTIL=0.0

    def test_natural_conjugations_reach_model(self):
        for phrase in (
            "podrías abrir las imágenes",
            "quiero que abras los documentos",
            "cierras la ventana de descargas",
            "cierre el explorador",
            "¿me copiarías el archivo a documentos?",
            "me buscas las reuniones de mañana",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(local_nlu._candidate(phrase))

    def test_destructive_or_informational_phrases_not_model_actions(self):
        for phrase in (
            "apaga mi ordenador", "elimina todos los archivos",
            "borra el escritorio", "ejecuta scripts",
            "cómo abrir imágenes", "por qué cerrar el explorador",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(local_nlu._candidate(phrase))

    def test_unrecognized_phrase_reports_why_ollama_was_not_used(self):
        with patch("hover_next.local_nlu.urlopen") as call:
            captured=io.StringIO()
            with redirect_stdout(captured):
                self.assertIsNone(local_nlu.model_intent("ahora es Spotify"))
        call.assert_not_called()
        self.assertIn("filtrado_sin_peticion_segura",captured.getvalue())

    def test_successful_classification_remains_strictly_allowlisted(self):
        packet={"message":{"content":json.dumps({
            "action":"pc_open_folder","location":"pictures"})}}
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=json.dumps(packet).encode()
        with patch("hover_next.local_nlu.urlopen",return_value=mock) as post:
            intent=local_nlu.model_intent("podrías abrir imágenes")
        self.assertEqual(intent.action,"pc_open_folder")
        self.assertEqual(intent.args["location"],"pictures")
        self.assertEqual(post.call_args.kwargs["timeout"],6.0)

    def test_model_returns_untrusted_action_without_running_it(self):
        packet={"message":{"content":json.dumps({
            "action":"pc_open_folder","location":"C:/Windows"})}}
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=json.dumps(packet).encode()
        with patch("hover_next.local_nlu.urlopen",return_value=mock):
            with redirect_stdout(io.StringIO()) as out:
                self.assertIsNone(local_nlu.model_intent("podrías abrir Windows"))
        self.assertIn("modelo_desconocido_o_respuesta_rechazada",out.getvalue())

    def test_offline_server_reports_failure_and_does_not_lock_out_all_commands(self):
        with patch("hover_next.local_nlu.urlopen",side_effect=OSError("connection refused")):
            with redirect_stdout(io.StringIO()) as out:
                self.assertIsNone(local_nlu.model_intent("podrías abrir imágenes"))
        self.assertIn("servidor_local_no_disponible",out.getvalue())
        self.assertGreater(local_nlu._MISSING_UNTIL,0)


class LocalModelDiagnosticsTests(unittest.TestCase):
    def test_reports_running_model_without_inference_or_authorizations(self):
        resp=MagicMock()
        resp.__enter__.return_value.read.return_value=json.dumps({
            "models":[{"name":"qwen2.5:3b"}]}).encode()
        with patch("hover_next.diagnostics.urlopen",return_value=resp) as get:
            self.assertIn("ACTIVO",diagnostics.ollama_status())
        self.assertEqual(get.call_args.args[0],
                         "http://127.0.0.1:11434/api/tags")
        self.assertLess(get.call_args.kwargs["timeout"],3)

    def test_reports_missing_model_vs_ollama_off(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({
            "models":[{"name":"llama3.2:3b"}]}).encode()
        with patch("hover_next.diagnostics.urlopen",return_value=response):
            self.assertIn("ollama pull qwen2.5:3b",diagnostics.ollama_status())
        with patch("hover_next.diagnostics.urlopen",
                   side_effect=OSError("connection refused")):
            self.assertIn("NO RESPONDE",diagnostics.ollama_status())

    def test_show_unknown_transcripts_without_printing_entire_log(self):
        log="[voz] Hover, abre las imágenes\n[accion] Sin coincidencia: abre las imágenes\n"
        log+="[nlu] servidor_local_no_disponible\n"
        self.assertEqual(diagnostics.latest_unknowns(log),["abre las imágenes"])
        with tempfile.TemporaryDirectory() as tmp:
            logpath=Path(tmp)/"voice.log"
            logpath.write_text("[launcher] Iniciando HOVER\n"+log,encoding="utf-8")
            output=io.StringIO()
            with patch("hover_next.diagnostics._running_hover_process",
                       return_value=1234), \
                 patch("hover_next.diagnostics.state_paths",
                       return_value=(Path(tmp)/"voice.pid",logpath)), \
                 patch("hover_next.diagnostics.ollama_status",
                       return_value="NO RESPONDE"), \
                 redirect_stdout(output):
                diagnostics.quick_check()
        self.assertIn("abre las imágenes",output.getvalue())
        self.assertIn("servidor_local_no_disponible",output.getvalue())


if __name__=="__main__":
    unittest.main()

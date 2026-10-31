"""Model-output and Google write regression tests; no live services or tokens."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from email import message_from_bytes
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from hover_next import local_nlu
from hover_next import google_workspace
from hover_next.intent import parse, Intent
from hover_next import pc_files


class StructuredNLUTests(unittest.TestCase):
    def setUp(self):
        local_nlu._CACHE.clear()
        local_nlu._MISSING_UNTIL=0.

    def test_model_covers_whisper_examples_without_hardcoded_phrases(self):
        data=[
            ("cierra las cargas",{"action":"pc_close_window","app":"downloads"},
             "pc_close_window",{"app":"downloads"}),
            ("abre imágenes",{"action":"pc_open_folder","location":"pictures"},
             "pc_open_folder",{"location":"pictures"}),
            ("crea un evento para mañana que diga reunión",
             {"action":"google_create_event","title":"reunión",
              "date_phrase":"mañana"},"google_create_event",
             {"title":"reunión","date_phrase":"mañana","time_phrase":""}),
            ("búscame correos del proveedor",
             {"action":"google_personal_search",
              "service":"gmail","query":"proveedor"},
             "google_personal_search",{"source":"gmail","query":"proveedor"}),
            ("crea un borrador de correo asunto informe texto terminado",
             {"action":"gmail_create_draft","subject":"informe","body":"terminado"},
             "gmail_create_draft",
             {"recipient":"","subject":"informe","body":"terminado"}),
        ]
        for utterance,object_,action,arguments in data:
            with self.subTest(text=utterance):
                got=local_nlu.validate(object_,utterance)
                self.assertIsNotNone(got)
                self.assertEqual(got.action,action)
                self.assertEqual(got.args,arguments)

    def test_ollama_chat_json_schema_is_used_with_local_endpoint(self):
        reply={"message":{"content":json.dumps({
            "action":"pc_open_folder","location":"pictures"})}}
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=json.dumps(reply).encode()
        with patch("hover_next.local_nlu.urlopen",return_value=mock) as network:
            got=local_nlu.model_intent("abre imágenes")
        self.assertEqual(got.action,"pc_open_folder")
        request=network.call_args.args[0]
        payload=json.loads(request.data.decode())
        self.assertEqual(request.full_url,"http://127.0.0.1:11434/api/chat")
        self.assertFalse(payload["stream"])
        self.assertIsInstance(payload["format"],dict)
        self.assertEqual(payload["options"]["temperature"],0)
        self.assertNotIn("tools",payload)
        self.assertEqual(payload["messages"][-1]["content"],"abre imágenes")

    def test_unknown_legacy_command_falls_back_to_model(self):
        with patch("hover_next.local_nlu.model_intent",
                   return_value=Intent("pc_open_folder",args={"location":"pictures"})):
            got=parse("Hover abre imágenes")
        self.assertEqual(got.action,"pc_open_folder")

    def test_model_cannot_execute_privileged_or_ungrounded_actions(self):
        tests=(
            ({"action":"pc_shutdown"},"abre imágenes"),
            ({"action":"pc_delete"},"abre imágenes"),
            ({"action":"windows_app","app":"powershell"},"ejecuta powershell"),
            ({"action":"pc_create","kind":"excel","location":"desktop",
              "name":"factura imaginaria"},"crea un archivo"),
            ({"action":"pc_transfer","operation":"move","pick":"name",
              "name":"secretos.txt","source":"downloads","destination":"desktop"},
             "mueve cualquier archivo"),
            ({"action":"google_create_event","title":"reunión",
              "date_phrase":"mañana"},"crea reunión hoy"),
            ({"action":"gmail_create_draft","recipient":"nadie@example.com",
              "subject":"informe"},"prepara borrador asunto informe"),
            ({"action":"google_personal_search","query":"test",
              "service":"all"},"busca test"),
            ({"action":"pc_open_folder","location":"C:/Windows"},"abre Windows"),
            ({"action":"pc_open_folder","location":"documents",
              "shell":"rm -rf"},"abre documentos"),
        )
        for output,said in tests:
            with self.subTest(output=output):
                self.assertIsNone(local_nlu.validate(output,said))

    def test_destructive_unknown_speech_never_reaches_model(self):
        for utterance in ("elimina todo", "apaga por favor",
                          "manda un correo", "ejecuta scripts", "instala cosas"):
            self.assertFalse(local_nlu._candidate(utterance))
        with patch("hover_next.local_nlu.urlopen") as http:
            self.assertIsNone(local_nlu.model_intent("elimina todo"))
        http.assert_not_called()

    def test_model_failure_preserves_normal_commands(self):
        with patch("hover_next.local_nlu.urlopen",side_effect=OSError("offline")):
            self.assertIsNone(local_nlu.model_intent("abre imágenes"))
        self.assertEqual(parse("Hover abre calculadora").action,"windows_app")

    def test_ambiguous_prompt_and_reply_are_rejected(self):
        with patch("hover_next.local_nlu.urlopen") as url:
            self.assertIsNone(local_nlu.model_intent("cómo abro imágenes"))
        url.assert_not_called()
        self.assertIsNone(local_nlu.validate(
            {"action":"pc_open_folder","location":"unknown"},
            "abre imágenes"))


class MissingEventTitleTests(unittest.TestCase):
    def setUp(self):
        local_nlu._CACHE.clear()
        local_nlu._MISSING_UNTIL=0.0

    def test_whisper_date_never_becomes_title(self):
        sentence="crea un evento en el calendario para mañana"
        for title in ("manana","mañana","","calendario","evento"):
            with self.subTest(title=title):
                result=local_nlu.validate({
                    "action":"google_create_event",
                    "title":title,"date_phrase":"mañana",
                    "time_phrase":""},sentence)
                self.assertIsNotNone(result)
                self.assertEqual(result.action,"google_event_title_needed")
                self.assertEqual(result.args,{
                    "date_phrase":"mañana","time_phrase":""})

    def test_event_with_clear_real_title_is_allowed(self):
        spoken="crea un evento para mañana que diga reunión de mantenimiento"
        got=local_nlu.validate({
            "action":"google_create_event",
            "title":"reunión de mantenimiento",
            "date_phrase":"mañana"},spoken)
        self.assertEqual(got.action,"google_create_event")
        self.assertEqual(got.args["title"],"reunión de mantenimiento")

    def test_handsfree_dialogue_asks_title_then_creates_exact_event(self):
        from hover_next.voice_coucou import VoiceDialogue
        actions=[]
        now=[100.0]
        missing=Intent("google_event_title_needed",args={
            "date_phrase":"mañana","time_phrase":""})
        dialogue=VoiceDialogue(
            lambda intent: actions.append(intent) or "Evento creado",
            lambda *a:None,clock=lambda:now[0])
        with patch("hover_next.local_nlu.model_intent",
                   return_value=missing), \
             patch("hover_next.voice_coucou.publish"):
            status=dialogue.process(
                "Oye Hover, crea un evento en el calendario para mañana.")
            self.assertEqual(status,"waiting")
            self.assertFalse(actions)
            self.assertIsNotNone(dialogue.pending_event)
            status=dialogue.process("Reunión de mantenimiento")
        self.assertEqual(status,"action")
        self.assertEqual(len(actions),1)
        self.assertEqual(actions[0].action,"google_create_event")
        self.assertEqual(actions[0].args,{
            "title":"Reunión de mantenimiento",
            "date_phrase":"mañana","time_phrase":""})

    def test_cancel_and_expire_never_write_events(self):
        from hover_next.voice_coucou import VoiceDialogue
        actions=[]
        now=[100.0]
        dialogue=VoiceDialogue(
            lambda intent: actions.append(intent) or "Evento creado",
            lambda *a:None,clock=lambda:now[0])
        with patch("hover_next.voice_coucou.publish"):
            dialogue._ask_event_title(Intent("google_event_title_needed",args={
                "date_phrase":"mañana","time_phrase":""}))
            self.assertEqual(dialogue.process("Cancela"),"cancel")
            self.assertFalse(actions)
            dialogue._ask_event_title(Intent("google_event_title_needed",args={
                "date_phrase":"mañana","time_phrase":""}))
            now[0]=146.0
            self.assertEqual(dialogue.process("Reunión"),"cancel")
            self.assertFalse(actions)

    def test_direct_structured_intent_skips_model_reinterpretation(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.execute.return_value="Evento creado"
        intent=Intent("google_create_event",args={
            "title":"Reunión","date_phrase":"mañana","time_phrase":""})
        with patch("hover_next.app.parse") as parser, \
             patch("hover_next.app.publish"):
            out=run_one(intent,executor,voice_mode=True)
        self.assertEqual(out,"Evento creado")
        parser.assert_not_called()
        executor.execute.assert_called_once_with(intent,confirmed=True)


class GoogleCalendarDraftTests(unittest.TestCase):
    def test_calendar_creates_tomorrow_all_day_with_exclusive_end(self):
        tz=ZoneInfo("America/Bogota")
        now=datetime(2026,10,31,9,0,tzinfo=tz)
        service=MagicMock()
        service.events().insert().execute.return_value={"id":"evt123"}
        with patch("hover_next.google_workspace._service",return_value=service):
            response=google_workspace.calendar_create_event(
                "reunión","mañana",timezone_name="America/Bogota",now=now)
        payload=service.events().insert.call_args.kwargs
        self.assertEqual(payload["calendarId"],"primary")
        self.assertEqual(payload["sendUpdates"],"none")
        self.assertEqual(payload["body"]["summary"],"reunión")
        self.assertEqual(payload["body"]["start"],{"date":"2026-11-01"})
        self.assertEqual(payload["body"]["end"],{"date":"2026-11-02"})
        self.assertIn("todo el día",response)

    def test_calendar_never_creates_on_ambiguous_date(self):
        with patch("hover_next.google_workspace._service") as build:
            with self.assertRaises(ValueError):
                google_workspace.calendar_create_event(
                    "reunión","algún día inventado")
        build.assert_not_called()

    def test_email_draft_is_real_mime_and_never_sent(self):
        api=MagicMock()
        api.users().drafts().create().execute.return_value={"id":"draft-123"}
        with patch("hover_next.google_workspace._service",return_value=api):
            result=google_workspace.gmail_create_draft(
                "Informe semanal","Trabajo terminado","test@example.com")
        api.users().messages().send.assert_not_called()
        call=api.users().drafts().create.call_args.kwargs
        raw=base64.urlsafe_b64decode(call["body"]["message"]["raw"])
        message=message_from_bytes(raw)
        self.assertEqual(message["To"],"test@example.com")
        self.assertEqual(message["Subject"],"Informe semanal")
        self.assertIn("Trabajo terminado",message.get_payload(decode=True).decode())
        self.assertIn("No se envió",result)

    def test_draft_without_recipient_is_allowed_and_not_sent(self):
        api=MagicMock()
        api.users().drafts().create().execute.return_value={"id":"d123"}
        with patch("hover_next.google_workspace._service",return_value=api):
            result=google_workspace.gmail_create_draft("Informe",body="Listo")
        self.assertIn("Borrador",result)
        api.users().messages().send.assert_not_called()

    def test_oauth_requests_write_scopes_for_calendar_and_drafts(self):
        from hover_next.google_auth import SCOPES
        self.assertIn("https://www.googleapis.com/auth/calendar.events",SCOPES["calendar"])
        self.assertIn("https://www.googleapis.com/auth/gmail.compose",SCOPES["gmail"])
        self.assertNotIn("https://mail.google.com/",SCOPES["gmail"])


if __name__=="__main__":
    unittest.main()

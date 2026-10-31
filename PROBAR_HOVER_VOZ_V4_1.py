"""Prueba offline del interprete HOVER; NO abre apps ni accede a microfono."""
import unittest
from unittest.mock import patch
import Asistente_Voz_HOVER_v4_1 as hover

class Interpretacion(unittest.TestCase):
    def test_variantes_reportadas(self):
        samples = [
            "oye joe accede a cati piti",
            "oye over allí se ha chat jep",
            "oye over accede a chat e pretende",
            "abre chat pete over",
            "oye over abre chat e pepe",
            "dejo el accede a calle petty",
        ]
        with patch.object(hover.webbrowser, "open", return_value=True) as opener,\
             patch.object(hover, "speak"), patch.object(hover, "notify") as notifier:
            for text in samples:
                ok,_=hover.process_utterance(text,False)
                self.assertTrue(ok,text)
            self.assertEqual(opener.call_count,len(samples))
            self.assertEqual(notifier.call_count,len(samples)*2)

    def test_acciones_y_wake(self):
        with patch.object(hover,"show_my_pc"),patch.object(hover,"open_spotify",return_value=True),\
             patch.object(hover,"speak"), patch.object(hover,"notify"):
            self.assertEqual(hover.process_utterance("oye hover abre mi pc",False),(True,False))
            self.assertEqual(hover.process_utterance("oye hover abre spotify",False),(True,False))
            self.assertEqual(hover.process_utterance("oye jover",False),(True,True))
            self.assertEqual(hover.process_utterance("abre chatgpt",False),(False,False))

    def test_sitios_y_alternativas(self):
        self.assertEqual(hover.resolve_site("chat e pepe"),"https://chatgpt.com/")
        self.assertEqual(hover.resolve_site("spotifai"),"https://open.spotify.com/")
        alt={"alternatives":[{"text":"oye over accede a chat e pretende","confidence":0.8},
                             {"text":"oye over xxx brum","confidence":0.9}]}
        self.assertIn("chat",hover.best_vosk_result(alt))

if __name__=="__main__":unittest.main(verbosity=2)

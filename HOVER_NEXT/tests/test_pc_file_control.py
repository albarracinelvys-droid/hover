"""File operations stay scoped, user-confirmed and never overwrite targets."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hover_next.intent import parse
from hover_next import pc_files
from hover_next.voice_coucou import VoiceDialogue


class SpokenPCCommands(unittest.TestCase):
    def test_real_whisper_zip_request_is_a_file_move_not_google_search(self):
        i=parse("Oye, puedes mover el último comprimido de descargas a escritorio.")
        self.assertEqual(i.action,"pc_transfer")
        self.assertTrue(i.requires_confirmation)
        self.assertEqual(i.args["from"],"downloads")
        self.assertEqual(i.args["to"],"desktop")
        self.assertEqual(i.args["kind"],"archive")
        self.assertEqual(i.args["operation"],"move")

    def test_copy_latest_pdf(self):
        i=parse("puedes copiar el último PDF de descargas a documentos")
        self.assertEqual(i.action,"pc_transfer")
        self.assertEqual(i.args["operation"],"copy")
        self.assertEqual(i.args["kind"],"pdf")

    def test_move_named_file(self):
        i=parse("mueve el archivo proyecto.zip de descargas al escritorio")
        self.assertEqual(i.action,"pc_transfer")
        self.assertEqual(i.args["name"],"proyecto.zip")

    def test_create_folder_explicit_location(self):
        i=parse("crea una carpeta llamada Informes en el escritorio")
        self.assertEqual(i.action,"pc_create")
        self.assertEqual(i.args["location"],"desktop")
        self.assertTrue(i.requires_confirmation)

    def test_rename_requires_confirmation(self):
        i=parse("renombra el archivo informe.txt en descargas a informe nuevo.txt")
        self.assertEqual(i.action,"pc_rename")
        self.assertEqual(i.args["old"],"informe.txt")
        self.assertEqual(i.args["new"],"informe nuevo.txt")
        self.assertTrue(i.requires_confirmation)

    def test_append_requires_confirmation(self):
        i=parse("agrega texto mantenimiento terminado al archivo notas.txt en documentos")
        self.assertEqual(i.action,"pc_append")
        self.assertEqual(i.args["name"],"notas.txt")
        self.assertTrue(i.requires_confirmation)

    def test_how_to_question_is_not_a_file_move(self):
        self.assertEqual(
            parse("como puedo mover el ultimo comprimido de descargas al escritorio").action,
            "google_search")

    def test_ambiguous_all_files_is_not_executed(self):
        self.assertNotEqual(
            parse("puedes mover todos los archivos del disco C al escritorio").action,
            "pc_transfer")

    def test_oye_followup_stays_on_pc(self):
        commands=[]
        dialogue=VoiceDialogue(lambda command:(commands.append(command) or "ok"),
                              lambda *args:None,clock=lambda:100)
        dialogue.recent_until=130
        self.assertEqual(
            dialogue.process("Oye, puedes mover el ultimo comprimido de descargas a escritorio"),
            "action")
        self.assertEqual(
            parse(commands[0]).action,"pc_transfer")


class FileOperations(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.dirs={k:root/k for k in ("downloads","desktop","documents","favorite")}
        for folder in self.dirs.values():
            folder.mkdir()
        fake=patch("hover_next.pc_files.location",
                   side_effect=lambda loc,config:self.dirs[loc])
        fake.start()
        self.addCleanup(fake.stop)

    def test_move_latest_archive_ignores_newer_nonarchives(self):
        zipfile=self.dirs["downloads"]/"backup.zip"
        zipfile.write_bytes(b"zip contents")
        (self.dirs["downloads"]/"noise.txt").write_text("later",encoding="utf-8")
        args={"operation":"move","pick":"latest","kind":"archive",
              "from":"downloads","to":"desktop"}
        ready=pc_files.prepare_transfer(args,{})
        self.assertEqual(ready["name"],"backup.zip")
        self.assertEqual(ready["pick"],"name")
        result=pc_files.perform("pc_transfer",ready,{})
        self.assertIn("backup.zip",result)
        self.assertFalse(zipfile.exists())
        self.assertEqual((self.dirs["desktop"]/"backup.zip").read_bytes(),b"zip contents")

    def test_copy_collision_does_not_overwrite(self):
        (self.dirs["downloads"]/"archivo.pdf").write_bytes(b"new")
        (self.dirs["desktop"]/"archivo.pdf").write_bytes(b"existing")
        args={"operation":"copy","pick":"name","name":"archivo.pdf",
              "from":"downloads","to":"desktop"}
        pc_files.perform("pc_transfer",args,{})
        self.assertEqual((self.dirs["desktop"]/"archivo.pdf").read_bytes(),b"existing")
        self.assertEqual((self.dirs["desktop"]/"archivo (2).pdf").read_bytes(),b"new")

    def test_selected_file_cannot_change_after_confirmation(self):
        file=self.dirs["downloads"]/"latest.zip"
        file.write_bytes(b"ABC")
        args={"operation":"move","pick":"latest","kind":"archive",
              "from":"downloads","to":"desktop"}
        ready=pc_files.prepare_transfer(args,{})
        file.write_bytes(b"changed after confirmation")
        with self.assertRaisesRegex(pc_files.PCFileError,"cambió"):
            pc_files.perform("pc_transfer",ready,{})
        self.assertTrue(file.exists())

    def test_rename_does_not_overwrite(self):
        (self.dirs["documents"]/"original.txt").write_text("hello",encoding="utf-8")
        (self.dirs["documents"]/"taken.txt").write_text("protected",encoding="utf-8")
        with self.assertRaisesRegex(pc_files.PCFileError,"existe"):
            pc_files.perform("pc_rename",{
                "location":"documents","old":"original.txt","new":"taken.txt"},{})
        self.assertEqual((self.dirs["documents"]/"taken.txt").read_text(),"protected")

    def test_create_folder_and_txt(self):
        pc_files.perform("pc_create",{
            "kind":"folder","location":"desktop","name":"Reportes"},{})
        pc_files.perform("pc_create",{
            "kind":"text","location":"desktop","name":"nota"},{})
        self.assertTrue((self.dirs["desktop"]/"Reportes").is_dir())
        self.assertEqual((self.dirs["desktop"]/"nota.txt").read_text(),"")

    def test_append_text_preserves_existing_content(self):
        file=self.dirs["documents"]/"notas.txt"
        file.write_text("Original\n",encoding="utf-8")
        pc_files.perform("pc_append",{
            "location":"documents","name":"notas.txt",
            "text":"Mantenimiento terminado"},{})
        self.assertEqual(file.read_text(encoding="utf-8"),
                         "Original\nMantenimiento terminado\n")

    def test_reject_relative_parent_traversal(self):
        with self.assertRaises(ValueError):
            pc_files.perform("pc_transfer",{
                "operation":"move","pick":"name","name":"../secret.txt",
                "from":"downloads","to":"desktop"},{})
        self.assertFalse((self.dirs["desktop"]/"secret.txt").exists())


if __name__=="__main__":
    unittest.main()

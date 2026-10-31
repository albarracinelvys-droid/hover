"""Local files are scoped; direct deletion only sends individual files to Trash."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from hover_next.intent import parse
from hover_next import pc_files
from hover_next.voice_coucou import VoiceDialogue


class SpokenPCCommands(unittest.TestCase):
    def test_real_whisper_zip_request_is_a_file_move_not_google_search(self):
        i=parse("Oye, puedes mover el último comprimido de descargas a escritorio.")
        self.assertEqual(i.action,"pc_transfer")
        self.assertFalse(i.requires_confirmation)
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
        self.assertFalse(i.requires_confirmation)

    def test_rename_requires_confirmation(self):
        i=parse("renombra el archivo informe.txt en descargas a informe nuevo.txt")
        self.assertEqual(i.action,"pc_rename")
        self.assertEqual(i.args["old"],"informe.txt")
        self.assertEqual(i.args["new"],"informe nuevo.txt")
        self.assertFalse(i.requires_confirmation)

    def test_append_requires_confirmation(self):
        i=parse("agrega texto mantenimiento terminado al archivo notas.txt en documentos")
        self.assertEqual(i.action,"pc_append")
        self.assertEqual(i.args["name"],"notas.txt")
        self.assertFalse(i.requires_confirmation)

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


class FileConfirmationFlow(unittest.TestCase):
    def test_latest_archive_runs_without_popup(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        executor.execute.return_value="Movido"
        snapshot={"operation":"move","pick":"name","kind":"archive",
                  "from":"downloads","to":"desktop","name":"backup.zip",
                  "size":"123","mtime_ns":"456"}
        with patch("hover_next.pc_files.prepare_transfer",return_value=snapshot), \
             patch("hover_next.app.confirm_voice_intent") as popup, \
             patch("hover_next.app.publish"):
            result=run_one(
                "Oye Hover, mueve el último comprimido de descargas al escritorio.",
                executor,voice_mode=True)
        self.assertEqual(result,"Movido")
        popup.assert_not_called()
        cmd=executor.execute.call_args.args[0]
        self.assertFalse(cmd.requires_confirmation)
        self.assertEqual(cmd.args["name"],"backup.zip")
        executor.execute.assert_called_once_with(cmd,confirmed=True)

    def test_invalid_selection_does_not_execute(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        with patch("hover_next.pc_files.prepare_transfer",
                   side_effect=pc_files.PCFileError("Not found")), \
             patch("hover_next.app.publish"):
            self.assertIsNone(run_one(
                "Oye Hover, mueve el último comprimido de descargas al escritorio.",
                executor,voice_mode=True))
        executor.execute.assert_not_called()


class DeleteVoiceTests(unittest.TestCase):
    def test_delete_latest_voice_runs_immediately(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        executor.execute.return_value="Envié ejemplo.zip a la Papelera."
        snapshot={"pick":"name","name":"ejemplo.zip",
                  "location":"desktop","size":"123","mtime_ns":"456"}
        with patch("hover_next.pc_files.prepare_delete",
                   return_value=snapshot) as prepare, \
             patch("hover_next.app.confirm_voice_intent") as popup, \
             patch("hover_next.app.publish"):
            result=run_one(
                "Hover, elimina el último archivo del escritorio.",
                executor,voice_mode=True)
        self.assertIn("Papelera",result)
        prepare.assert_called_once()
        popup.assert_not_called()
        cmd=executor.execute.call_args.args[0]
        self.assertEqual(cmd.action,"pc_delete")
        self.assertFalse(cmd.requires_confirmation)
        self.assertEqual(cmd.args,snapshot)
        executor.execute.assert_called_once_with(cmd,confirmed=True)

    def test_delete_named_voice_runs_without_yes_or_no(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        executor.execute.return_value="Envié factura.pdf a la Papelera."
        snapshot={"pick":"name","name":"factura.pdf",
                  "location":"downloads","size":"7","mtime_ns":"8"}
        with patch("hover_next.pc_files.prepare_delete",return_value=snapshot), \
             patch("hover_next.app.confirm_voice_intent") as popup, \
             patch("hover_next.app.publish"):
            result=run_one(
                "Oye Hover elimina el archivo factura.pdf de descargas",
                executor,voice_mode=True)
        self.assertIn("factura.pdf",result)
        popup.assert_not_called()
        executor.execute.assert_called_once()

    def test_voice_dialogue_routes_delete_directly(self):
        executed=[]
        d=VoiceDialogue(lambda text:executed.append(text) or "Enviado a la Papelera",
                        lambda *args:None,clock=lambda:100)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(
                d.process("Hover, elimina el último archivo del escritorio."),
                "action")
        self.assertEqual(len(executed),1)
        self.assertEqual(parse(executed[0]).action,"pc_delete")

    def test_delete_missing_file_does_not_execute(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        with patch("hover_next.pc_files.prepare_delete",
                   side_effect=pc_files.PCFileError("No existe")), \
             patch("hover_next.app.publish"):
            result=run_one("Hover elimina el último archivo del escritorio",
                           executor,voice_mode=True)
        self.assertIsNone(result)
        executor.execute.assert_not_called()

    def test_real_whisper_phrase_is_not_a_google_search(self):
        for phrase in (
            "Oye Hover, que elimina el último archivo movido al escritorio.",
            "Hover elimina el último archivo movido al escritorio.",
            "Hover, borra el último archivo que moviste al escritorio.",
        ):
            with self.subTest(phrase=phrase):
                intent=parse(phrase)
                self.assertEqual(intent.action,"pc_delete")
                self.assertFalse(intent.requires_confirmation)
                self.assertEqual(intent.args,{"pick":"last_moved",
                                              "location":"desktop"})

    def test_last_moved_without_record_fails_instead_of_deleting_latest(self):
        from hover_next.app import run_one
        executor=MagicMock()
        executor.config={}
        with patch("hover_next.pc_files.prepare_delete",
                   side_effect=pc_files.PCFileError("No hay movimiento reciente")), \
             patch("hover_next.app.publish"):
            result=run_one(
                "Oye Hover que elimina el último archivo movido al escritorio",
                executor,voice_mode=True)
        self.assertIsNone(result)
        executor.execute.assert_not_called()

    def test_delete_grammar_recognizes_del_escritorio(self):
        for command in (
            "elimina el último archivo de escritorio",
            "elimina el último archivo del escritorio",
            "eliminar el último archivo del escritorio",
            "borra el último comprimido de descargas",
            "elimina el archivo factura.pdf de descargas",
        ):
            with self.subTest(command=command):
                intent=parse(command)
                self.assertEqual(intent.action,"pc_delete")
                self.assertFalse(intent.requires_confirmation)
        self.assertNotEqual(
            parse("elimina el directorio Windows").action,"pc_delete")
        self.assertNotEqual(
            parse("elimina todos los archivos del sistema").action,"pc_delete")


class FileOperations(unittest.TestCase):
    def setUp(self):
        # Isolate the per-session last successful movement between tests.
        pc_files._LAST_MOVED=None
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

    def test_last_moved_deletion_targets_actual_move_not_latest_file(self):
        import sys
        src=self.dirs["downloads"]/"archivo-real.zip"
        src.write_bytes(b"moved by HOVER")
        (self.dirs["desktop"]/"no-tocar.txt").write_text(
            "personal document",encoding="utf-8")
        args={"operation":"move","pick":"name","name":src.name,
              "from":"downloads","to":"desktop"}
        pc_files.perform("pc_transfer",args,{})
        # Another file can be newer and must NOT be chosen as the target.
        unrelated=self.dirs["desktop"]/"despues.pdf"
        unrelated.write_text("never delete me",encoding="utf-8")
        frozen=pc_files.prepare_delete(
            {"pick":"last_moved","location":"desktop"},{})
        self.assertEqual(frozen["name"],"archivo-real.zip")
        sent=MagicMock()
        with patch.dict(sys.modules,{"send2trash":MagicMock(send2trash=sent)}):
            pc_files.perform("pc_delete",frozen,{})
        sent.assert_called_once_with(
            str(self.dirs["desktop"]/"archivo-real.zip"))
        self.assertTrue(unrelated.exists())
        with self.assertRaises(pc_files.PCFileError):
            pc_files.prepare_delete(
                {"pick":"last_moved","location":"desktop"},{})

    def test_last_moved_rejects_file_modified_after_move(self):
        moved=self.dirs["downloads"]/"movido.zip"
        moved.write_bytes(b"version one")
        pc_files.perform("pc_transfer",{
            "operation":"move","pick":"name","name":"movido.zip",
            "from":"downloads","to":"desktop"},{})
        (self.dirs["desktop"]/"movido.zip").write_bytes(b"changed content")
        with self.assertRaisesRegex(pc_files.PCFileError,"cambió"):
            pc_files.prepare_delete(
                {"pick":"last_moved","location":"desktop"},{})

    def test_last_moved_rejects_wrong_folder_and_old_history(self):
        moved=self.dirs["downloads"]/"movido.zip"
        moved.write_bytes(b"copy")
        pc_files.perform("pc_transfer",{
            "operation":"move","pick":"name","name":"movido.zip",
            "from":"downloads","to":"desktop"},{})
        with self.assertRaises(pc_files.PCFileError):
            pc_files.prepare_delete(
                {"pick":"last_moved","location":"documents"},{})
        with patch("hover_next.pc_files.time.monotonic",
                   return_value=pc_files._LAST_MOVED["when"]+3600):
            with self.assertRaises(pc_files.PCFileError):
                pc_files.prepare_delete(
                    {"pick":"last_moved","location":"desktop"},{})

    def test_last_moved_is_not_inferred_after_hove_restart(self):
        # Different sessions have no shared last-move guess.
        (self.dirs["desktop"]/"personal.pdf").write_bytes(b"important")
        with self.assertRaises(pc_files.PCFileError):
            pc_files.prepare_delete(
                {"pick":"last_moved","location":"desktop"},{})

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

    def test_trash_uses_send2trash(self):
        import sys
        src=self.dirs["downloads"]/"factura.pdf"
        src.write_bytes(b"test")
        args=pc_files.prepare_delete({
            "pick":"name","name":"factura.pdf","location":"downloads"},{})
        sender=MagicMock()
        with patch.dict(sys.modules,{"send2trash":MagicMock(send2trash=sender)}):
            result=pc_files.perform("pc_delete",args,{})
        sender.assert_called_once_with(str(src))
        self.assertIn("Papelera",result)

    def test_trash_requires_frozen_target(self):
        src=self.dirs["downloads"]/"factura.pdf"
        src.write_bytes(b"test")
        with self.assertRaises(pc_files.PCFileError):
            pc_files.perform("pc_delete",{
                "pick":"name","name":"factura.pdf","location":"downloads"},{})
        self.assertTrue(src.exists())

    def test_trash_rejects_changed_file(self):
        src=self.dirs["downloads"]/"factura.pdf"
        src.write_bytes(b"test")
        frozen=pc_files.prepare_delete({
            "pick":"name","name":"factura.pdf","location":"downloads"},{})
        src.write_bytes(b"modified")
        with self.assertRaisesRegex(pc_files.PCFileError,"cambió"):
            pc_files.perform("pc_delete",frozen,{})
        self.assertTrue(src.exists())

    def test_trash_rejects_directory(self):
        (self.dirs["downloads"]/"reports").mkdir()
        with self.assertRaises(pc_files.PCFileError):
            pc_files.prepare_delete({
                "pick":"name","name":"reports","location":"downloads"},{})

    def test_reject_relative_parent_traversal(self):
        with self.assertRaises(ValueError):
            pc_files.perform("pc_transfer",{
                "operation":"move","pick":"name","name":"../secret.txt",
                "from":"downloads","to":"desktop"},{})
        self.assertFalse((self.dirs["desktop"]/"secret.txt").exists())


class ExtendedPCVoiceTests(unittest.TestCase):
    def test_create_named_folders_excel_word_text_csv(self):
        examples=(
            ("Hover crea una carpeta llamada Proyectos en el escritorio",
             "folder","proyectos","desktop"),
            ("Hover crea carpeta Informes en documentos",
             "folder","informes","documents"),
            ("Hover crea un archivo Excel llamado inventario en documentos",
             "excel","inventario","documents"),
            ("Hover crea un documento de Word llamado Informe en el escritorio",
             "word","informe","desktop"),
            ("Oye Hover crea un TXT llamado notas en descargas",
             "text","notas","downloads"),
            ("Hover crea un archivo csv llamado ventas en el escritorio",
             "csv","ventas","desktop"),
            ("Hover crea carpeta Pruebas","folder","pruebas","desktop"),
        )
        for spoken,kind,name,loc in examples:
            with self.subTest(spoken=spoken):
                intent=parse(spoken)
                self.assertEqual(intent.action,"pc_create")
                self.assertEqual(intent.args,{"kind":kind,"name":name,"location":loc})
                self.assertFalse(intent.requires_confirmation)

    def test_no_name_asks_for_next_utterance(self):
        for spoken,kind,loc in (
            ("Hover crea una carpeta","folder","desktop"),
            ("Hover crea un Excel en documentos","excel","documents"),
            ("Hover crea un archivo Word","word","desktop"),
            ("Hover crea un CSV en descargas","csv","downloads"),
        ):
            with self.subTest(spoken=spoken):
                intent=parse(spoken)
                self.assertEqual(intent.action,"pc_name_needed")
                self.assertEqual(intent.args,{"kind":kind,"location":loc})

    def test_close_only_foreground_window(self):
        for speech,app in (
            ("Hover cierra la ventana actual","foreground"),
            ("Oye Hover cierra Excel","excel"),
            ("Hover cierra Word","word"),
            ("Hover cierra la calculadora","calculator"),
            ("Hover cerrar el bloc de notas","notepad"),
        ):
            with self.subTest(speech=speech):
                got=parse(speech)
                self.assertEqual(got.action,"pc_close_window")
                self.assertEqual(got.args["app"],app)
                self.assertFalse(got.requires_confirmation)

    def test_questions_do_not_mutate_windows(self):
        for speech in ("Hover como se crea una hoja de excel",
                       "Hover que es una carpeta",
                       "Hover puedes explicarme como cerrar Word",
                       "Hover elimina todos los archivos de Windows"):
            intent=parse(speech)
            self.assertNotIn(intent.action,("pc_create","pc_delete","pc_close_window"))

    def test_voice_two_turn_creates_excel_with_exact_name(self):
        commands=[]
        dialogue=VoiceDialogue(
            lambda cmd:commands.append(cmd) or "ok",lambda *args:None,
            clock=lambda:100)
        with patch("hover_next.voice_coucou.publish"):
            self.assertEqual(dialogue.process("Hover crea un excel en documentos"),"action")
            self.assertEqual(dialogue.pending_kind,"excel")
            self.assertEqual(dialogue.process("Control industrial"),"action")
        self.assertEqual(parse(commands[-1]).action,"pc_create")
        self.assertEqual(parse(commands[-1]).args,{
            "kind":"excel","name":"control industrial","location":"documents"})


class SavedOfficeFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        fake=patch("hover_next.pc_files.location",
                   side_effect=lambda loc,conf:self.root)
        fake.start()
        self.addCleanup(fake.stop)

    def test_excel_is_valid_openpyxl_workbook(self):
        from openpyxl import load_workbook
        result=pc_files.perform("pc_create",{
            "kind":"excel","name":"inventario","location":"desktop"},{})
        target=self.root/"inventario.xlsx"
        self.assertIn("inventario.xlsx",result)
        book=load_workbook(target,read_only=True)
        self.assertEqual(book.sheetnames,["Hoja1"])
        book.close()

    def test_word_is_valid_docx(self):
        from docx import Document
        pc_files.perform("pc_create",{
            "kind":"word","name":"informe","location":"documents"},{})
        target=self.root/"informe.docx"
        self.assertTrue(target.exists())
        self.assertEqual(len(Document(target).paragraphs),0)

    def test_csv_txt_and_folder_are_created(self):
        for kind,name,suffix in (
            ("csv","datos",".csv"),("text","notas",".txt")):
            pc_files.perform("pc_create",{
                "kind":kind,"name":name,"location":"downloads"},{})
            self.assertTrue((self.root/(name+suffix)).is_file())
        pc_files.perform("pc_create",{
            "kind":"folder","name":"Trabajo","location":"desktop"},{})
        self.assertTrue((self.root/"Trabajo").is_dir())

    def test_existing_excel_is_not_overwritten(self):
        target=self.root/"inventario.xlsx"
        target.write_bytes(b"DO NOT DELETE")
        with self.assertRaises(pc_files.PCFileError):
            pc_files.perform("pc_create",{
                "kind":"excel","name":"inventario","location":"desktop"},{})
        self.assertEqual(target.read_bytes(),b"DO NOT DELETE")

    def test_refuses_filename_disguised_as_executable(self):
        for name in ("malware.exe","../../../outside","reporte.docx"):
            with self.subTest(name=name):
                with self.assertRaises((ValueError,pc_files.PCFileError)):
                    pc_files.perform("pc_create",{
                        "kind":"excel","name":name,"location":"desktop"},{})
        self.assertFalse((self.root/"malware.exe").exists())


class SafeWindowCloseTests(unittest.TestCase):
    def test_close_sends_wm_close_not_taskkill(self):
        import sys
        win32gui=MagicMock()
        win32con=MagicMock(WM_CLOSE=16)
        win32gui.GetForegroundWindow.return_value=123
        win32gui.GetWindowText.return_value="Libro1 - Excel"
        win32gui.GetClassName.return_value="XLMAIN"
        win32gui.IsWindowVisible.return_value=True
        with patch.dict(sys.modules,{"win32gui":win32gui,"win32con":win32con}):
            result=pc_files.close_foreground_window("excel")
        self.assertIn("Libro1",result)
        win32gui.PostMessage.assert_called_once_with(123,16,0,0)

    def test_does_not_close_another_application(self):
        import sys
        win32gui=MagicMock()
        win32gui.GetForegroundWindow.return_value=123
        win32gui.GetWindowText.return_value="Libro1 - Excel"
        win32gui.GetClassName.return_value="XLMAIN"
        win32gui.IsWindowVisible.return_value=True
        with patch.dict(sys.modules,{"win32gui":win32gui,"win32con":MagicMock()}):
            with self.assertRaises(pc_files.PCFileError):
                pc_files.close_foreground_window("word")
        win32gui.PostMessage.assert_not_called()

    def test_does_not_close_hover(self):
        import sys
        gui=MagicMock()
        gui.GetForegroundWindow.return_value=123
        gui.GetWindowText.return_value="HOVER - Cuenta Google"
        gui.GetClassName.return_value="Window"
        gui.IsWindowVisible.return_value=True
        with patch.dict(sys.modules,{"win32gui":gui,"win32con":MagicMock()}):
            with self.assertRaises(pc_files.PCFileError):
                pc_files.close_foreground_window("foreground")
        gui.PostMessage.assert_not_called()



if __name__=="__main__":
    unittest.main()

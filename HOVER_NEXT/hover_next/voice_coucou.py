"""HOVER voice engine v5: Coucou-style adaptive speech detection and local STT.

Microphone capture never waits for recognition: streaming audio and ASR run in
separate threads. Supports "Hover, abre calculadora", "Oye Hover", and F8
(push-to-command fallback). No synthesized speech, no alert sounds.
"""
from __future__ import annotations

from queue import Empty, Full, Queue
import threading
import time

import numpy as np

from .audio_coucou import AdaptiveVad, FRAME, resample_frame, normalize_audio
from .intent import Intent, parse
from .wake import extract_wake
from .ui_bridge import publish
from .recognizers import create_recognizer


class VoiceDialogue:
    """Wake -> command -> brief contextual follow-ups, all without speech output.

    A name requested for a safe new file or a private repository can be
    dictated in the next utterance without repeating the wake word.
    Unrequested background audio never creates files or repositories.
    """
    def __init__(self, execute, send_dictated, clock=time.monotonic,
                 *, prepare_delete=None, execute_confirmed=None):
        self.execute = execute
        self.send_dictated = send_dictated
        self.clock = clock
        self.prepare_delete = prepare_delete
        self.execute_confirmed = execute_confirmed
        self.pending_delete = None
        self.delete_until = 0.0
        self.command_until = 0.0
        self.ptt_until = 0.0
        self.dictation_provider = ""
        self.dictation_until = 0.0
        self.pending_kind = ""
        self.pending_until = 0.0
        self.pending_repo_private_required = False
        self.recent_until = 0.0
        self.recent_action = ""

    def press_hotkey(self):
        self.ptt_until = self.clock() + 10.0
        publish("listening", "Comando por F8")
        print("[F8] Di ahora tu orden, sin decir Hover.",flush=True)

    def _ask_name(self, kind, *, private_required=False):
        if kind not in ("txt","excel","folder","repo"):
            return
        self.pending_kind = kind
        self.pending_until = self.clock()+45.0
        self.pending_repo_private_required = (kind=="repo" and private_required)
        prompt = (
            'Di el nombre y termina con "en privado"'
            if self.pending_repo_private_required else
            "Dime SOLO el nombre para "+("repositorio privado" if kind=="repo" else kind)
        )
        print("[dialogo]",prompt,flush=True)
        publish("listening",prompt,3)

    def _handle_name(self, spoken):
        from .spoken_names import spoken_name
        from .wake import normalize_speech
        clean = normalize_speech(spoken)
        if clean in ("cancela","cancelar","no","olvidalo","cancelalo"):
            self.pending_kind=""
            self.pending_repo_private_required=False
            publish("ok","Solicitud cancelada")
            print("[dialogo] Cancelado por voz.",flush=True)
            return "cancel"
        kind=self.pending_kind
        if (kind=="repo" and self.pending_repo_private_required and
                not __import__("re").search(r"\bprivad[oa]\b",clean)):
            publish("listening",'Di el nombre y termina con "en privado"',3)
            print("[dialogo] Falta indicar que el repositorio será privado.",flush=True)
            return "waiting"
        name=spoken_name(spoken,kind)
        if not name:
            print("[dialogo] Nombre poco claro; sigo esperando un nombre corto.",flush=True)
            publish("listening","Repite solo el nombre",3)
            return "waiting"
        self.pending_kind=""
        self.pending_repo_private_required=False
        if kind=="repo":
            command=f"crea un repositorio privado llamado {name}"
        elif kind=="folder":
            command=f"crea una subcarpeta llamada {name}"
        elif kind=="excel":
            command=f"en la carpeta favorita crea un Excel llamado {name}"
        else:
            command=f"en la carpeta favorita crea un TXT llamado {name}"
        print("[dialogo] Nombre dictado:",name,"| Acción:",kind,flush=True)
        return self._command(command)

    def process(self, spoken: str):
        spoken=spoken.strip()
        if not spoken:
            return "silence"
        now=self.clock()
        print("[voz]",spoken,flush=True)
        from .wake import normalize_speech
        normalized=normalize_speech(spoken)
        remainder=extract_wake(spoken)
        # A destructive request never runs on its first utterance.
        # A separate, exact spoken "sí" during this short window is required.
        if self.pending_delete is not None:
            response=normalize_speech(remainder if remainder is not None else spoken)
            if now>=self.delete_until:
                self.pending_delete=None
                publish("ok","Eliminación cancelada: confirmación vencida.",3)
                print("[papelera] Confirmación caducada; nada eliminado.",flush=True)
                return "cancel"
            if response in ("no","cancela","cancelar","no elimines","no borrar"):
                self.pending_delete=None
                publish("ok","Eliminación cancelada.",3)
                print("[papelera] Cancelado por voz.",flush=True)
                return "cancel"
            if response in ("si","si confirmo","confirmo"):
                confirmed=self.pending_delete
                self.pending_delete=None  # Never replay an authorization.
                self.delete_until=0.0
                if self.execute_confirmed is None:
                    publish("error","Falta el ejecutor seguro de la Papelera.")
                    return "failed"
                result=self.execute_confirmed(confirmed)
                return "action" if result is not None else "failed"
            # Ignore unrelated voice while waiting; do not accidentally run it.
            publish("listening","Para eliminar di SÍ; para cancelar di NO",3)
            print("[papelera] Espero solo 'sí' o 'no'.",flush=True)
            return "waiting"
        if self.pending_kind and now>=self.pending_until:
            self.pending_kind=""
            self.pending_repo_private_required=False
        if self.dictation_provider and now>=self.dictation_until:
            self.dictation_provider=""

        # A wake phrase can start another command even during a pending name.
        if remainder is not None:
            self.ptt_until=0.0
            self.dictation_provider=""
            if not remainder:
                self.command_until=now+12.0
                self.recent_until=now+45.0
                publish("listening","Te escucho")
                print("[wake] HOVER detectado. Di tu orden.",flush=True)
                return "wake"
            # Keep the raw transcription for Google: the normalized wake
            # detector deliberately strips symbols like C++ and accents.
            from .information_queries import remove_wake_preserving_text
            raw_command=remove_wake_preserving_text(spoken)
            parsed=parse(raw_command if raw_command is not None else remainder)
            if self.pending_kind and parsed.action=="unknown":
                return self._handle_name(remainder)
            self.pending_kind=""
            self.command_until=0.0
            command_text=(raw_command if raw_command is not None and
                          parsed.action in ("google_search","google_translate")
                          else remainder)
            return self._command(command_text)

        # HOVER prompted for this slot; don't require the wake phrase again.
        if self.pending_kind and now<self.pending_until:
            # When Whisper drops HOVER but keeps "Oye", an explicit safe
            # replacement request may supersede the pending name.
            if normalized.startswith("oye "):
                candidate=normalized[4:].strip()
                replacement=parse(candidate)
                safe={"local_name_needed","create_local","google_search",
                      "google_app","windows_app","office_new","open_link",
                      "media_key","spotify_play","spotify_resume"}
                if replacement.action in safe:
                    print("[dialogo] Cambiando solicitud pendiente a:",candidate,flush=True)
                    self.pending_kind=""
                    return self._command(candidate)
            return self._handle_name(spoken)

        if self.dictation_provider and now<self.dictation_until:
            provider=self.dictation_provider
            self.dictation_provider=""
            if normalized in ("cancela","cancelar","no enviar"):
                publish("ok","Dictado cancelado")
                return "cancel"
            return self.send_dictated(provider,spoken)

        # Voice-session context allows "Reprodúcelo" after opening Spotify,
        # without permanently listening for arbitrary unlabeled commands.
        if (now<self.recent_until
                and self.recent_action in ("spotify_play","spotify_resume")
                and normalized in ("reproducelo","ponlo","dale play",
                                   "reanuda","reproduce","dale reproducir")):
            return self._command("reproducelo")

        if now<self.command_until or now<self.ptt_until:
            if normalized in ("oye","hey","si","ok","hola","hover"):
                self.command_until=max(self.command_until,now+8.0)
                print("[listening] Espero la orden completa.",flush=True)
                return "waiting"
            self.command_until=self.ptt_until=0.0
            return self._command(spoken)

        # Whisper sometimes drops "Hover" but retains "Oye". Permit only
        # explicit low-risk follow-up commands inside a recent HOVER dialogue.
        if now<self.recent_until and normalized.startswith("oye "):
            candidate=normalized[4:].strip()
            intent=parse(candidate)
            allow={"local_name_needed","create_local","google_search",
                   "google_app","windows_app","office_new","open_link",
                   "media_key","spotify_play","spotify_resume","open_site",
                   "pc_transfer","pc_rename","pc_create","pc_append"}
            if intent.action in allow:
                print("[dialogo] Orden de seguimiento con 'Oye':",candidate,flush=True)
                return self._command(candidate)

        print("[idle] No se reconocio el nombre Hover. Prueba F8.",flush=True)
        return "ignored"

    def _command(self,utterance):
        command=parse(utterance)
        if command.action=="unknown":
            publish("error","Orden no reconocida: "+utterance[:50])
            print("[accion] Sin coincidencia:",utterance,flush=True)
            return "unknown"
        print("[accion]",command.action,command.args,flush=True)
        if command.action=="pc_delete":
            # Freeze an exact filename before speaking confirmation.
            if self.prepare_delete is None or self.execute_confirmed is None:
                publish("error","La confirmación por voz de la Papelera no está disponible.")
                return "failed"
            try:
                frozen=self.prepare_delete(command)
            except Exception as exc:
                print("[papelera] No se pudo preparar:",type(exc).__name__,
                      str(exc),flush=True)
                publish("error","No encontré un archivo válido para eliminar.",3)
                return "failed"
            if (frozen.action!="pc_delete" or
                    not frozen.requires_confirmation or
                    frozen.args.get("pick")!="name"):
                publish("error","La eliminación no es válida.",3)
                return "failed"
            self.pending_delete=frozen
            self.delete_until=self.clock()+20.0
            name=frozen.args["name"]
            question=(f"¿Enviar {name} a la Papelera? "
                      "Responde SÍ o NO por voz.")
            publish("listening",question,3)
            print("[papelera]",question,flush=True)
            return "waiting"
        # The ASR sometimes says "que ya me" or "que llame" for a repo name.
        # Do not create a possibly misnamed repo. Ask for the name alone.
        from .wake import normalize_speech
        sentence=normalize_speech(utterance)
        if (command.action=="create_private_repo" and
                ("que ya me" in sentence or "que llame " in sentence)):
            self._ask_name("repo")
            return "waiting"

        result=self.execute(utterance)
        if result is None:
            return "failed"
        self.recent_until=self.clock()+45.0
        self.recent_action=command.action
        if command.action=="chat_prepare":
            self.dictation_provider=command.provider
            self.dictation_until=self.clock()+65.0
            publish("listening","Dicta tu mensaje para "+command.provider)
            print("[dictado] Di tu mensaje ahora; no necesitas Hover.",flush=True)
        elif command.action=="repo_name_needed":
            self._ask_name("repo",private_required=bool(command.args.get("require_private")))
        elif command.action=="local_name_needed":
            self._ask_name(command.args.get("kind","txt"))
        return "action"


def mic_test(device=None, threshold=0.0008, seconds=12.0):
    from .voice import test_microphone
    return test_microphone(device=device,threshold=threshold)


def _hotkey_pressed():
    # No keyboard hooks; a harmless poll for F8 on Windows.
    import sys
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)
    except Exception:
        return False


def run(executor, *, engine="auto", model="small",
        device=None, threshold=0.0008):
    import sounddevice as sd
    from .app import run_one, run_confirmed_delete

    publish("thinking","Cargando motor local")
    recognizer = create_recognizer(engine, model)
    info = sd.query_devices(device,kind="input")
    sample_rate = int(round(info["default_samplerate"]))
    if sample_rate <= 0:
        sample_rate=48000
    input_frames = int(round(sample_rate*0.03))
    audio_queue = Queue(maxsize=180)
    work_queue = Queue(maxsize=4)
    vad = AdaptiveVad(minimum_rms=threshold)
    stop = threading.Event()
    error = []

    def send_dictated(provider,spoken):
        print("[dictado]",provider,spoken,flush=True)
        try:
            publish("thinking","Enviando mensaje a "+provider)
            result = executor.execute(
                Intent("chat_send_prepared",provider=provider,
                       args={"prompt":spoken}),confirmed=True
            )
            publish("ok",str(result),3)
            print("[ok]",result,flush=True)
            return "action"
        except Exception as exc:
            publish("error",str(exc))
            print("[error]",type(exc).__name__,str(exc),flush=True)
            return "failed"

    def freeze_delete(intent):
        from .pc_files import prepare_delete
        args=prepare_delete(intent.args,executor.config)
        return Intent(intent.action,intent.provider,args,intent.requires_confirmation)

    dialogue = VoiceDialogue(
        lambda command:run_one(command,executor,voice_mode=True),
        send_dictated,prepare_delete=freeze_delete,
        execute_confirmed=lambda intent:run_confirmed_delete(intent,executor))

    def recognizer_worker():
        try:
            while not stop.is_set():
                try:
                    samples = work_queue.get(timeout=0.2)
                except Empty:
                    continue
                if isinstance(samples,tuple) and len(samples)==3 and samples[0]=="google":
                    try:
                        from .google_ipc import execute_control
                        result=execute_control(samples[1],samples[2])
                        print("[google]",result,flush=True)
                    except Exception as exc:
                        print("[google] Error de autorización:",type(exc).__name__,str(exc),flush=True)
                        publish("error","Google: revisa la conexión OAuth.")
                    finally:
                        work_queue.task_done()
                    continue
                print(f"[asr] Transcribiendo {len(samples)/16000:.1f}s con {recognizer.name}",flush=True)
                try:
                    text = recognizer.transcribe(normalize_audio(samples))
                    if text:
                        # Reject characteristic Whisper silence hallucinations.
                        noisy_phrases=("subtitulos realizados","subtitulos por la comunidad",
                                       "hasta la proxima","suscribete","amara.org")
                        from .wake import normalize_speech
                        cleaned = normalize_speech(text)
                        if any(phrase in cleaned for phrase in noisy_phrases):
                            print("[asr] Fragmento descartado por ruido.",flush=True)
                        else:
                            dialogue.process(text)
                    else:
                        print("[asr] No hubo palabras claras. Intenta hablar mas cerca.",flush=True)
                except Exception as exc:
                    print("[asr] Error:",type(exc).__name__,exc,flush=True)
                    publish("error",str(exc))
                finally:
                    work_queue.task_done()
        except Exception as exc:
            error.append(exc)
            stop.set()
        finally:
            # A Playwright synchronous browser must be closed by the same thread
            # that started it. Never attempt this from the microphone thread.
            try:
                executor.browser.close()
                print("[chat] Chrome de HOVER cerrado desde su hilo.",flush=True)
            except Exception as exc:
                print("[chat] Error controlado al cerrar Chrome:",exc,flush=True)

    def callback(indata, frame_count, ti, status):
        if status:
            print("[mic] Aviso del controlador:",status,flush=True)
        try:
            audio_queue.put_nowait(indata[:,0].copy())
        except Full:
            try:audio_queue.get_nowait()
            except Empty:pass
            try:audio_queue.put_nowait(indata[:,0].copy())
            except Full:pass

    worker=threading.Thread(target=recognizer_worker,name="HOVER-LocalASR",daemon=True)
    worker.start()
    publish("idle","HOVER listo")
    print(f"[ready] HOVER v5 | {recognizer.name} | {info['name']} | "
          f"dispositivo={device if device is not None else 'predeterminado'} "
          f"| {sample_rate} Hz",flush=True)
    print("[ready] Di 'Hover, abre calculadora' o pulsa F8 y di 'abre calculadora'. "
          "Sin voz, sin pitidos.",flush=True)
    print("[ready] El reconocimiento transcurre en paralelo al microfono.",flush=True)
    last_meter=time.monotonic()
    last_google_poll=0.0
    try:
        from .google_ipc import write_status
        write_status("HOVER escuchando. Gestiona Google desde Atajos.")
    except OSError:
        pass
    f8_was_down=False
    try:
        with sd.InputStream(samplerate=sample_rate,device=device,channels=1,
                            blocksize=input_frames,dtype="float32",callback=callback):
            while not stop.is_set():
                now=time.monotonic()
                if now-last_google_poll>=0.8:
                    last_google_poll=now
                    from .google_ipc import poll_control
                    job=poll_control()
                    if job:
                        try:
                            work_queue.put_nowait(("google",job[0],job[1]))
                            publish("thinking","Google: "+job[0]+" "+job[1],3)
                        except Full:
                            publish("error","Google: cola ocupada; reintenta.",3)
                f8_down=_hotkey_pressed()
                if f8_down and not f8_was_down:
                    dialogue.press_hotkey()
                f8_was_down=f8_down
                try:
                    raw=audio_queue.get(timeout=0.08)
                except Empty:
                    if error:break
                    continue
                frame=resample_frame(raw,FRAME)
                segment=vad.feed(frame)
                now=time.monotonic()
                if now-last_meter>=5.0:
                    print(f"[mic] RMS={vad.rms:.5f} "
                          f"umbral_adaptativo={vad.threshold:.5f} "
                          f"voz={'si' if vad.active else 'no'} "
                          f"cola={work_queue.qsize()}",flush=True)
                    last_meter=now
                if segment is not None:
                    try:
                        work_queue.put_nowait(segment)
                    except Full:
                        print("[asr] Cola llena, se descarto un segmento antiguo.",flush=True)
    except KeyboardInterrupt:
        print("[idle] HOVER detenido por el usuario.",flush=True)
    finally:
        stop.set()
        worker.join(timeout=2.0)
        publish("idle","")
    if error:
        raise RuntimeError("El reconocedor se detuvo: "+str(error[0]))

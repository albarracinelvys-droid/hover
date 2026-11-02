"""HOVER voice engine v5: Coucou-style adaptive speech detection and local STT.

Microphone capture never waits for recognition: streaming audio and ASR run in
separate threads. Supports "Hover, abre calculadora", "Oye Hover", and F8
(push-to-command fallback). No synthesized speech, no alert sounds.
"""
from __future__ import annotations

from queue import Empty, Full, Queue
import os
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
    def __init__(self, execute, send_dictated, clock=time.monotonic):
        self.execute = execute
        self.send_dictated = send_dictated
        self.clock = clock
        self.command_until = 0.0
        self.ptt_until = 0.0
        self.dictation_provider = ""
        self.dictation_until = 0.0
        self.pending_kind = ""
        self.pending_until = 0.0
        self.pending_pc_location = ""
        self.pending_event = None
        self.pending_event_until = 0.0
        self.recent_until = 0.0
        self.recent_action = ""

    def press_hotkey(self):
        self.ptt_until = self.clock() + 10.0
        publish("listening", "Comando por F8")
        print("[F8] Di ahora tu orden, sin decir Hover.",flush=True)

    def _ask_name(self, kind, location=""):
        if kind not in ("txt","excel","folder","repo","word","csv"):
            return
        self.pending_kind = kind
        self.pending_pc_location = location
        self.pending_until = self.clock()+45.0
        prompt = "Dime SOLO el nombre para "+("repositorio privado" if kind=="repo" else kind)
        print("[dialogo]",prompt,flush=True)
        publish("listening",prompt,3)

    def _handle_name(self, spoken):
        from .spoken_names import spoken_name
        from .wake import normalize_speech
        clean = normalize_speech(spoken)
        if clean in ("cancela","cancelar","no","olvidalo","cancelalo"):
            self.pending_kind=""
            publish("ok","Solicitud cancelada")
            print("[dialogo] Cancelado por voz.",flush=True)
            return "cancel"
        kind=self.pending_kind
        name=spoken_name(spoken,kind)
        if not name:
            print("[dialogo] Nombre poco claro; sigo esperando un nombre corto.",flush=True)
            publish("listening","Repite solo el nombre",3)
            return "waiting"
        self.pending_kind=""
        place=self.pending_pc_location
        self.pending_pc_location=""
        if place:
            labels={"desktop":"escritorio","downloads":"descargas",
                    "documents":"documentos","favorite":"carpeta favorita"}
            destination=labels.get(place,"escritorio")
            noun={"folder":"carpeta","excel":"archivo excel",
                  "word":"archivo word","txt":"txt","csv":"csv"}[kind]
            command=f"crea un {noun} llamado {name} en el {destination}"
        elif kind=="repo":
            command=f"crea un repositorio privado llamado {name}"
        elif kind=="folder":
            command=f"crea una subcarpeta llamada {name}"
        elif kind=="excel":
            command=f"en la carpeta favorita crea un Excel llamado {name}"
        else:
            command=f"en la carpeta favorita crea un TXT llamado {name}"
        print("[dialogo] Nombre dictado:",name,"| Acción:",kind,flush=True)
        return self._command(command)

    def _ask_event_title(self, intent):
        # A generic date like 'mañana' is never a title. Preserve the
        # parsed date and ask for a *separate* name without another wake word.
        self.pending_event=dict(intent.args)
        self.pending_event_until=self.clock()+45.0
        message="¿Cómo se llamará el evento? Di solo el título."
        print("[calendar]",message,flush=True)
        publish("listening",message,3)

    def _finish_event_title(self, spoken):
        import re
        from .wake import normalize_speech
        from .information_queries import remove_wake_preserving_text
        raw=remove_wake_preserving_text(spoken)
        title=(raw if raw is not None else spoken).strip(" .,!?:¿¡")
        title=re.sub(
            r"^(?:que se llame|que diga|ll[aá]malo|t[ií]tulo)\\s+",
            "",title,flags=re.IGNORECASE).strip()
        normalized=normalize_speech(title)
        if normalized in ("cancela","cancelar","no","olvidalo","cancelalo"):
            self.pending_event=None
            publish("ok","Evento cancelado; no creé nada.",3)
            print("[calendar] Cancelado por voz.",flush=True)
            return "cancel"
        if (not 2<=len(title)<=120 or
                normalized in ("hover","oye","si","hoy","manana","calendario","evento")
                or re.match(r"^(?:abre|cierra|elimina|borra|apaga|ejecuta|instala)\\b",
                            normalized)):
            publish("listening","Repite solo el título del evento.",3)
            return "waiting"
        details=self.pending_event
        self.pending_event=None
        if not details:
            return "failed"
        final=Intent("google_create_event",args={
            "title":title,
            "date_phrase":details["date_phrase"],
            "time_phrase":details.get("time_phrase","")})
        print("[calendar] Título dictado:",title,flush=True)
        result=self.execute(final)
        if result is None:
            return "failed"
        self.recent_action="google_create_event"
        self.recent_until=self.clock()+45.0
        return "action"

    def process(self, spoken: str):
        spoken=spoken.strip()
        if not spoken:
            return "silence"
        now=self.clock()
        print("[voz]",spoken,flush=True)
        from .wake import normalize_speech
        normalized=normalize_speech(spoken)
        remainder=extract_wake(spoken)
        if self.pending_event is not None:
            if now>=self.pending_event_until:
                self.pending_event=None
                publish("ok","Solicitud de evento vencida. No se creó nada.",3)
                return "cancel"
            # Follow-up can have "Hover" or not. The title is not fed
            # through the LLM as a new command.
            if remainder != "" and normalized not in ("hover","oye hover"):
                return self._finish_event_title(spoken)
            publish("listening","Dime solo el título del evento.",3)
            return "waiting"
        if self.pending_kind and now>=self.pending_until:
            self.pending_kind=""
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
            return self._command(command_text,preparsed=parsed)

        # HOVER prompted for this slot; don't require the wake phrase again.
        if self.pending_kind and now<self.pending_until:
            # When Whisper drops HOVER but keeps "Oye", an explicit safe
            # replacement request may supersede the pending name.
            if normalized.startswith("oye "):
                candidate=normalized[4:].strip()
                replacement=parse(candidate)
                safe={"local_name_needed","create_local","google_search",
                      "google_app","windows_app","office_new","open_link",
                      "media_key","spotify_open","spotify_play","spotify_resume",
                      "pc_close_window","pc_create","pc_name_needed"}
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
                and self.recent_action in ("spotify_open","spotify_open","spotify_play","spotify_resume")
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
                   "media_key","spotify_open","spotify_play","spotify_resume","open_site",
                   "pc_transfer","pc_rename","pc_create","pc_append"}
            if intent.action in allow:
                print("[dialogo] Orden de seguimiento con 'Oye':",candidate,flush=True)
                return self._command(candidate,preparsed=intent)

        print("[idle] No se reconocio el nombre Hover. Prueba F8.",flush=True)
        return "ignored"

    def _command(self,utterance,preparsed=None):
        # Reuse the parsed action; don't call the local model twice.
        command=preparsed if preparsed is not None else parse(utterance)
        if command.action=="unknown":
            publish("error","Orden no reconocida: "+utterance[:50])
            print("[accion] Sin coincidencia:",utterance,flush=True)
            return "unknown"
        print("[accion]",command.action,command.args,flush=True)
        if command.action=="google_event_title_needed":
            self._ask_event_title(command)
            return "waiting"
        # The ASR sometimes says "que ya me" or "que llame" for a repo name.
        # Do not create a possibly misnamed repo. Ask for the name alone.
        from .wake import normalize_speech
        sentence=normalize_speech(utterance)
        if (command.action=="create_private_repo" and
                ("que ya me" in sentence or "que llame " in sentence)):
            self._ask_name("repo")
            return "waiting"

        # The live dispatcher consumes a validated Intent directly; test
        # callbacks and explicit private-repo authorization keep spoken text.
        deliver=(command if getattr(self.execute,"_hover_accepts_intent",False)
                 and command.action!="create_private_repo" else utterance)
        result=self.execute(deliver)
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
            self._ask_name("repo")
        elif command.action=="pc_name_needed":
            self._ask_name(command.args["kind"],command.args["location"])
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
    from .app import run_one

    publish("thinking","Cargando motor local")
    recognizer = create_recognizer(engine, model)
    info = sd.query_devices(device,kind="input")
    sample_rate = int(round(info["default_samplerate"]))
    if sample_rate <= 0:
        sample_rate=48000
    input_frames = int(round(sample_rate*0.03))
    audio_queue = Queue(maxsize=180)
    work_queue = Queue(maxsize=4)
    command_queue = Queue(maxsize=4)
    google_queue = Queue(maxsize=8)
    try:
        pause_ms = int(os.environ.get("HOVER_VAD_PAUSE_MS", "750"))
    except ValueError:
        pause_ms = 750
    vad = AdaptiveVad(minimum_rms=threshold,
                      hangover_frames=max(10, min(40, round(pause_ms/30))))
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

    def voice_dispatch(command):
        return run_one(command,executor,voice_mode=True)

    voice_dispatch._hover_accepts_intent=True
    dialogue = VoiceDialogue(voice_dispatch,send_dictated)

    # Calendar refresh is independent of the audio/Whisper worker. The notch
    # only reads a small local snapshot while the user opens its Calendar tab.
    from .calendar_bridge import start_background
    start_background(stop)
    # Start the local Windows Media bridge automatically; it supplies current
    # track title, album art, state and button commands to Windhawk without a
    # separate PowerShell process.
    from .media_bridge import start_background as start_media_bridge
    start_media_bridge(stop)

    def recognizer_worker():
        try:
            while not stop.is_set():
                try:
                    samples = work_queue.get(timeout=0.2)
                except Empty:
                    continue
                samples,queued_at=samples
                started_at=time.monotonic()
                queue_ms=(started_at-queued_at)*1000
                print(f"[asr] Transcribiendo {len(samples)/16000:.1f}s con {recognizer.name}",flush=True)
                try:
                    text = recognizer.transcribe(normalize_audio(samples))
                    asr_ms=(time.monotonic()-started_at)*1000
                    handoff_start=time.monotonic()
                    if text:
                        # Reject characteristic Whisper silence hallucinations.
                        noisy_phrases=("subtitulos realizados","subtitulos por la comunidad",
                                       "hasta la proxima","suscribete","amara.org")
                        from .wake import normalize_speech
                        cleaned = normalize_speech(text)
                        if any(phrase in cleaned for phrase in noisy_phrases):
                            print("[asr] Fragmento descartado por ruido.",flush=True)
                        else:
                            try:
                                command_queue.put_nowait((text,time.monotonic()))
                            except Full:
                                print("[accion] Cola llena; repite tu orden.",flush=True)
                                publish("error","HOVER ocupado; repite la orden.",3)
                    else:
                        print("[asr] No hubo palabras claras. Intenta hablar mas cerca.",flush=True)
                    handoff_ms=(time.monotonic()-handoff_start)*1000
                    print(f"[latencia] cola={queue_ms:.0f}ms "
                          f"asr={asr_ms:.0f}ms "
                          f"entrega_accion={handoff_ms:.0f}ms "
                          f"total={(time.monotonic()-queued_at)*1000:.0f}ms",
                          flush=True)
                except Exception as exc:
                    print("[asr] Error:",type(exc).__name__,exc,flush=True)
                    publish("error",str(exc))
                finally:
                    work_queue.task_done()
        except Exception as exc:
            error.append(exc)
            stop.set()
    def command_worker():
        # Serial delivery preserves follow-up context; blocking apps and Ollama
        # cannot stop the ASR worker from accepting the next voice segment.
        try:
            while not stop.is_set():
                try:
                    transcript,queued_at=command_queue.get(timeout=0.2)
                except Empty:
                    continue
                started_at=time.monotonic()
                wait_ms=(started_at-queued_at)*1000
                try:
                    dialogue.process(transcript)
                except Exception as exc:
                    print("[accion] Error:",type(exc).__name__,exc,flush=True)
                    publish("error",str(exc))
                finally:
                    action_ms=(time.monotonic()-started_at)*1000
                    print(f"[latencia] cola_accion={wait_ms:.0f}ms "
                          f"interpretacion_y_accion={action_ms:.0f}ms",flush=True)
                    command_queue.task_done()
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


    def google_worker():
        # OAuth and Google network calls are serial on their own thread so
        # authorization never stalls speech transcription.
        while not stop.is_set():
            try:
                service,operation=google_queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                from .google_ipc import execute_control
                result=execute_control(service,operation)
                print("[google]",result,flush=True)
            except Exception as exc:
                print("[google] Error de autorización:",
                      type(exc).__name__,str(exc),flush=True)
                publish("error","Google: revisa la conexión OAuth.")
            finally:
                google_queue.task_done()

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
    command_thread=threading.Thread(target=command_worker,name="HOVER-Commands",daemon=True)
    google_thread=threading.Thread(target=google_worker,name="HOVER-GoogleOAuth",daemon=True)
    worker.start()
    command_thread.start()
    google_thread.start()

    def warm_nlu_worker():
        # Warm after mic and ASR initialization. Never delay audio capture.
        if not stop.wait(3.0):
            from .local_nlu import warm_model
            warm_model()

    threading.Thread(target=warm_nlu_worker,name="HOVER-QwenWarmup",
                     daemon=True).start()
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
                            google_queue.put_nowait((job[0],job[1]))
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
                        work_queue.put_nowait((segment,time.monotonic()))
                    except Full:
                        print("[asr] Cola llena, se descarto un segmento antiguo.",flush=True)
    except KeyboardInterrupt:
        print("[idle] HOVER detenido por el usuario.",flush=True)
    finally:
        stop.set()
        worker.join(timeout=2.0)
        command_thread.join(timeout=2.0)
        google_thread.join(timeout=1.0)
        publish("idle","")
    if error:
        raise RuntimeError("El reconocedor se detuvo: "+str(error[0]))

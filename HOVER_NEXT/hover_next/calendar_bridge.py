"""Read-only Google Calendar to the local Windhawk calendar tab.

No credentials leave the OAuth client. The bridge contains only bounded event
summaries, dates, and validated Google Calendar links; no token, emails,
attendees, or event descriptions. Network reads never run on microphone thread.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import tempfile
import threading
import time
import uuid

BRIDGE_NAME="calendar_events.tsv"
REFRESH_INTERVAL=120
_MAX_EVENTS=250
_WAKE=threading.Event()
_STARTED=False
_START_LOCK=threading.Lock()


def _bridge_path():
    path=Path(tempfile.gettempdir())/"WindhawkIslandPremium"
    path.mkdir(parents=True,exist_ok=True)
    return path/BRIDGE_NAME


def _clean(value,length=95):
    return re.sub(r"[\t\r\n\\x00-\\x1f]+"," "," ".join(str(value).split()))[:length]


def _google_link(raw):
    from urllib.parse import urlparse
    if not isinstance(raw,str) or len(raw)>700:
        return ""
    p=urlparse(raw)
    if p.scheme!="https" or p.hostname!="calendar.google.com":
        return ""
    if p.username or p.password:
        return ""
    return raw.replace("\t","").replace("\r","").replace("\n","")


def _event_date(event):
    start=event.get("start",{})
    value=start.get("date") or start.get("dateTime","")
    if not isinstance(value,str):
        return ""
    # ISO dates from Google's Calendar API, never model-supplied.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value[:10]):
        try:
            datetime.fromisoformat(value[:10])
        except ValueError:
            return ""
        return value[:10]
    return ""


def read_calendar_events(now=None):
    """Fetch bounded events over a 14-month window with event dates."""
    from .google_workspace import _service
    now=now or datetime.now(timezone.utc)
    api=_service("calendar","calendar","v3")
    start=now-timedelta(days=45)
    finish=now+timedelta(days=420)
    result=[]
    token=None
    while len(result)<_MAX_EVENTS:
        params={
            "calendarId":"primary",
            "timeMin":start.isoformat(),
            "timeMax":finish.isoformat(),
            "singleEvents":True,
            "orderBy":"startTime",
            "maxResults":min(250,_MAX_EVENTS-len(result)),
            "fields":"nextPageToken,items(summary,start(date,dateTime),htmlLink)",
        }
        if token:
            params["pageToken"]=token
        response=api.events().list(**params).execute()
        for event in response.get("items",[]):
            date=_event_date(event)
            if date:
                result.append((date,_clean(event.get("summary") or "(Sin título)"),
                               _google_link(event.get("htmlLink",""))))
            if len(result)>=_MAX_EVENTS:
                break
        token=response.get("nextPageToken")
        if not token:
            break
    return result


def write_snapshot(events, *, status="ok"):
    """Atomic local read-only snapshot. Never writes OAuth tokens."""
    if status not in ("ok","offline","disconnected"):
        raise ValueError("calendar bridge state invalid")
    lines=["status\t"+status]
    for date,title,link in list(events)[:_MAX_EVENTS]:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date):
            continue
        lines.append(date+"\t"+_clean(title)+"\t"+_google_link(link))
    target=_bridge_path()
    tmp=target.with_name(target.name+"."+uuid.uuid4().hex+".tmp")
    try:
        tmp.write_text("\n".join(lines)+"\n",encoding="utf-8")
        os.replace(tmp,target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def refresh():
    from .google_auth import credentials,GoogleAuthError
    try:
        # A token's existence is insufficient: validate expiry and scopes.
        credentials("calendar")
        events=read_calendar_events()
    except (GoogleAuthError,ImportError):
        write_snapshot([] ,status="disconnected")
        return False
    except Exception as exc:
        # No private error details in an on-screen bridge.
        print("[calendar-ui] Actualización no disponible:",type(exc).__name__,
              flush=True)
        # Do not erase successful events because the network failed briefly.
        if not _bridge_path().exists():
            write_snapshot([],status="offline")
        return False
    write_snapshot(events,status="ok")
    return True


def request_refresh():
    """Schedule refresh without blocking Whisper."""
    _WAKE.set()


def start_background(stop_event):
    """At most one daemon per HOVER process; task stops with voice engine."""
    global _STARTED
    with _START_LOCK:
        if _STARTED:
            return
        _STARTED=True

    def loop():
        global _STARTED
        try:
            while not stop_event.is_set():
                refresh()
                _WAKE.clear()
                until=time.monotonic()+REFRESH_INTERVAL
                while not stop_event.is_set() and not _WAKE.is_set():
                    stop_event.wait(timeout=min(1.0,max(0,until-time.monotonic())))
                    if time.monotonic()>=until:
                        break
        finally:
            _STARTED=False
    threading.Thread(target=loop,daemon=True,name="hover-google-calendar").start()

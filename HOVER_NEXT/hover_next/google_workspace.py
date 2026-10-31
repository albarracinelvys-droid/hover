"""Read-only Google account searches and narrowly scoped Docs creation.

Results stay local until the user explicitly requests to share them with
ChatGPT or Claude. Search returns metadata/snippets only (max 5 per source).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlparse

from . import google_auth as oauth


@dataclass(frozen=True)
class Item:
    source: str
    title: str
    description: str
    url: str

    def preview(self):
        return f"[{self.source}] {self.title} — {self.description[:160]} ({self.url})"


def _service(name,api,version):
    from googleapiclient.discovery import build
    return build(api,version,credentials=oauth.credentials(name),
                 cache_discovery=False)


def _bounded_term(q):
    q=" ".join(q.split())
    if not 2<=len(q)<=140:
        raise ValueError("Dime qué quieres buscar en tu cuenta Google.")
    return q


def _drive_query(term, docs_only=False):
    # Escape Drive v3 query literals, never interpolate arbitrary operators.
    clean=term.replace("\\","\\\\").replace("'","\\'")
    kind = " and mimeType = 'application/vnd.google-apps.document'" if docs_only else ""
    return f"trashed = false{kind} and (name contains '{clean}' or fullText contains '{clean}')"


def drive_search(query, limit=5,docs_only=False):
    term=_bounded_term(query)
    api=_service("drive","drive","v3")
    # Search by each of up to 3 distinct terms and merge client-side.
    # Drive's contains semantics are prefix-oriented for name/fullText,
    # so searching the full sentence alone usually misses results.
    tokens=list(dict.fromkeys(x for x in re.findall(r"[\w-]+",term) if len(x)>=3))[:3]
    terms=tokens or [term]
    seen=set()
    result=[]
    for part in terms:
        response=api.files().list(
            q=_drive_query(part,docs_only),fields="nextPageToken, files(id,name,mimeType,webViewLink,description,modifiedTime)",
            pageSize=min(30,limit*3),spaces="drive").execute()
        for file in response.get("files",[]):
            fid=file.get("id","")
            if fid in seen:continue
            seen.add(fid)
            mime=file.get("mimeType","")
            link=file.get("webViewLink","")
            if mime=="application/vnd.google-apps.document" and not link:
                link=f"https://docs.google.com/document/d/{fid}/edit"
            if not _safe_link(link):
                link=""
            result.append(Item(
                "Docs" if mime=="application/vnd.google-apps.document" else "Drive",
                file.get("name","Sin nombre")[:160],
                file.get("description","")[:200],
                link,
            ))
            if len(result)>=limit:return result
    return result


def _safe_link(value):
    if not value:return False
    parsed=urlparse(value)
    return (parsed.scheme=="https" and
            parsed.hostname in (
                "drive.google.com","docs.google.com","sheets.google.com",
                "slides.google.com","mail.google.com","calendar.google.com"))


def gmail_search(query,limit=5):
    term=_bounded_term(query)
    api=_service("gmail","gmail","v1")
    listing=api.users().messages().list(
        userId="me",q=term,maxResults=limit).execute()
    items=[]
    for item in listing.get("messages",[])[:limit]:
        message=api.users().messages().get(
            userId="me",id=item["id"],format="metadata",
            metadataHeaders=["Subject","From"]).execute()
        headers={x.get("name","").lower():x.get("value","")
                 for x in message.get("payload",{}).get("headers",[])}
        subject=headers.get("subject","(Sin asunto)")
        sender=headers.get("from","")
        snippet=message.get("snippet","")
        tid=message.get("threadId","")
        link=f"https://mail.google.com/mail/u/0/#all/{tid}" if tid else ""
        items.append(Item("Gmail",subject[:160],
                          (sender+" "+snippet)[:220],link))
    return items


def calendar_search(query,limit=5):
    term=_bounded_term(query)
    api=_service("calendar","calendar","v3")
    now=datetime.now(timezone.utc)
    result=api.events().list(
        calendarId="primary",q=term,
        timeMin=(now-timedelta(days=30)).isoformat(),
        timeMax=(now+timedelta(days=180)).isoformat(),
        maxResults=limit,orderBy="startTime",singleEvents=True).execute()
    return [
        Item("Calendar",evt.get("summary","(Sin título)")[:160],
             (evt.get("start",{}).get("dateTime") or
              evt.get("start",{}).get("date",""))+" "+
             evt.get("description","")[:120],
             evt.get("htmlLink","") if _safe_link(evt.get("htmlLink","")) else "")
        for evt in result.get("items",[])[:limit]
    ]


def docs_create(title):
    title=" ".join(title.strip().split())
    if not 2<=len(title)<=120:
        raise ValueError("El documento necesita un título corto.")
    # drive.file restricts write access to the Docs this app creates/opens.
    api=_service("docs","docs","v1")
    document=api.documents().create(body={"title":title}).execute()
    docid=document.get("documentId","")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,160}",docid):
        raise RuntimeError("Google no devolvió un ID de documento verificable.")
    return Item("Docs",title,"Documento nuevo creado por HOVER",
                f"https://docs.google.com/document/d/{docid}/edit")


def calendar_create_event(title, date_phrase, time_phrase="", *,
                          timezone_name="America/Bogota", now=None):
    """Create one event at a parsed local date; without hour, ALL DAY.

    No attendee invitations, recurrence, fuzzy dates or invented time zones.
    """
    from zoneinfo import ZoneInfo
    from dateparser import parse as parse_date
    from datetime import date as date_type
    title=" ".join(str(title).split())
    date_phrase=" ".join(str(date_phrase).split())
    time_phrase=" ".join(str(time_phrase).split())
    if not 2<=len(title)<=120 or not 2<=len(date_phrase)<=100:
        raise ValueError("El evento necesita un título y una fecha.")
    try:
        zone=ZoneInfo(timezone_name)
    except (ValueError,KeyError) as exc:
        raise ValueError("La zona horaria configurada no es válida.") from exc
    local_now=now or datetime.now(zone)
    parsed=parse_date(
        date_phrase+(" "+time_phrase if time_phrase else ""),
        languages=["es"],
        settings={"RELATIVE_BASE":local_now,
                  "PREFER_DATES_FROM":"future",
                  "TIMEZONE":timezone_name,
                  "RETURN_AS_TIMEZONE_AWARE":True})
    if parsed is None:
        raise ValueError("No entendí la fecha del evento. Indica una fecha clara.")
    parsed=parsed.astimezone(zone)
    if parsed.date()<local_now.date() or parsed.date()>(local_now+timedelta(days=366)).date():
        raise ValueError("La fecha está fuera del intervalo permitido.")
    if not time_phrase:
        day=parsed.date()
        body={"summary":title,
              "start":{"date":day.isoformat()},
              "end":{"date":(day+timedelta(days=1)).isoformat()}}
    else:
        if parsed<=local_now or parsed>(local_now+timedelta(days=366)):
            raise ValueError("El evento debe tener hora futura.")
        body={"summary":title,
              "start":{"dateTime":parsed.isoformat(),"timeZone":timezone_name},
              "end":{"dateTime":(parsed+timedelta(hours=1)).isoformat(),
                     "timeZone":timezone_name}}
    api=_service("calendar","calendar","v3")
    created=api.events().insert(calendarId="primary",body=body,
                                sendUpdates="none").execute()
    if not isinstance(created,dict) or not created.get("id"):
        raise RuntimeError("Google no confirmó que el evento se haya creado.")
    # Refresh the Windhawk calendar asynchronously; no extra Google call
    # on the microphone thread.
    from .calendar_bridge import request_refresh
    request_refresh()
    return f"Evento {title} creado en Calendar para {parsed.date().isoformat()}"+(
        " (todo el día)." if not time_phrase else f" a las {parsed.strftime('%H:%M')}.")


def gmail_create_draft(subject, body="", recipient=""):
    """Create a draft, NEVER send the message or infer recipient addresses."""
    import base64
    from email.message import EmailMessage
    subject=" ".join(str(subject).split())
    body=str(body)
    recipient=str(recipient).strip()
    if not 2<=len(subject)<=150 or "\r" in subject or "\n" in subject:
        raise ValueError("El borrador requiere un asunto claro.")
    if len(body)>2000:
        raise ValueError("El cuerpo del mensaje es demasiado largo.")
    if recipient and not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",recipient):
        raise ValueError("El destinatario debe tener una dirección de correo válida.")
    message=EmailMessage()
    if recipient:
        message["To"]=recipient
    message["Subject"]=subject
    message.set_content(body)
    encoded=base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    api=_service("gmail","gmail","v1")
    response=api.users().drafts().create(
        userId="me",body={"message":{"raw":encoded}}).execute()
    if not isinstance(response,dict) or not response.get("id"):
        raise RuntimeError("Google no confirmó la creación del borrador.")
    return f"Borrador guardado en Gmail: {subject}. No se envió ningún correo."


def search_all(query,sources=None):
    """Only search services that already have local authorization."""
    _bounded_term(query)
    enabled=oauth.status()
    if sources:
        sources=tuple(x for x in sources if x in oauth.SERVICES)
    else:
        sources=oauth.SERVICES
    results=[]
    errors=[]
    for key in sources:
        if not enabled.get(key):
            continue
        try:
            if key=="drive":
                results+=drive_search(query)
            elif key=="gmail":
                results+=gmail_search(query)
            elif key=="calendar":
                results+=calendar_search(query)
            elif key=="docs" and not enabled.get("drive"):
                # Docs API does not offer a document list endpoint.
                # Docs search requires Drive metadata search consent.
                errors.append("Para buscar los Docs conecta también Google Drive.")
        except Exception as exc:
            # No credential content or third-party response body in user logs.
            errors.append(f"{key}: {type(exc).__name__}. Revisa la autorización y la API.")
    return results[:20],errors


def format_results(items, max_chars=1800):
    if not items:
        return "No encontré resultados en los servicios Google conectados."
    payload="Resultados encontrados en mi cuenta Google:\n"
    for i,item in enumerate(items,1):
        line=f"{i}. {item.preview()}\n"
        if len(payload)+len(line)>max_chars:
            break
        payload+=line
    return payload

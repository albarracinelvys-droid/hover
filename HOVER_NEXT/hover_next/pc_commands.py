"""Conservative Spanish voice grammar for local PC file actions.

Only fully specified requests are operations; questions remain searches.
"""
from __future__ import annotations

import re


LOC = r"(descargas|escritorio|documentos|carpeta favorita)"
LOCATIONS = {
    "descargas":"downloads",
    "escritorio":"desktop",
    "documentos":"documents",
    "carpeta favorita":"favorite",
}


def _clean(t):
    t=t.strip(" 	.,!?¿¡")
    # Polite imperatives must not be mistaken for Google questions.
    t=re.sub(r"^(?:oye|hey|por favor)[, ]+", "", t)
    t=re.sub(r"^(?:(?:me )?puedes|(?:me )?podrias|quiero que|necesito que)\s+", "", t)
    return t.strip()


def _where(t):
    return LOCATIONS[t]


def parse_pc_command(text: str):
    """Return (action,args) for a bounded file command, or None."""
    t=_clean(text)
    # "Oye, puedes mover el último comprimido de descargas a escritorio."
    # The complete pattern is assembled here to avoid ambiguous free-form
    # path extraction. No shell paths or recursively searched files.
    transfer=(r"(mueve|mover|traslada|trasladar|copia|copiar)\s+"
        r"(?:el|la)?\s*(?:ultimo|ultima|mas reciente)\s+"
        r"(?:(?:archivo|fichero)\s+)?"
        r"(comprimido|zip|rar|pdf|excel|imagen|foto|texto|txt|archivo|fichero|documento)\s+"
        r"(?:de|desde|en)\s+(?:(?:la|el)\s+)?(?:(?:carpeta de|carpeta)\s+)?"
        +LOC+
        r"\s+(?:a|al|hacia)\s+(?:(?:el|la|mi)\s+)?"+LOC)
    m=re.fullmatch(transfer,t)
    if m:
        verb,kind,src,dest=m.groups()
        types={"comprimido":"archive","zip":"archive","rar":"archive",
               "pdf":"pdf","excel":"excel","imagen":"image","foto":"image",
               "texto":"text","txt":"text"}
        return "pc_transfer", {
            "operation":"copy" if verb in ("copia","copiar") else "move",
            "pick":"latest","kind":types.get(kind,"any"),
            "from":_where(src),"to":_where(dest)
        }

    # Recycle Bin only: explicit local file deletion runs at once.
    # Ambiguous filenames, folders and system paths remain unsupported.
    delete_latest=(r"(?:elimina|eliminar|borra|borrar)\s+"
        r"(?:el|la)?\s*(?:ultimo|ultima|mas reciente)\s+"
        r"(?:(?:archivo|fichero)\s+)?"
        r"(comprimido|zip|rar|pdf|excel|imagen|foto|texto|txt|archivo|fichero|documento)\s+"
        r"(?:de|del|desde|en)\s+(?:(?:la|el)\s+)?(?:(?:carpeta de|carpeta)\s+)?"
        +LOC)
    m=re.fullmatch(delete_latest,t)
    if m:
        kind, folder=m.groups()
        types={"comprimido":"archive","zip":"archive","rar":"archive",
               "pdf":"pdf","excel":"excel","imagen":"image","foto":"image",
               "texto":"text","txt":"text"}
        return "pc_delete",{"pick":"latest","kind":types.get(kind,"any"),
                            "location":_where(folder)}

    delete_named=(r"(?:elimina|eliminar|borra|borrar)\s+"
        r"(?:(?:el|la)\s+)?(?:archivo|fichero)\s+(.+?)\s+"
        r"(?:de|del|desde|en)\s+(?:(?:la|el)\s+)?"+LOC)
    m=re.fullmatch(delete_named,t)
    if m:
        name,folder=m.groups()
        return "pc_delete",{"pick":"name","name":name.strip(),
                            "location":_where(folder)}

    # A specific file must be identified by its basename and folder.
    named=(r"(mueve|mover|traslada|trasladar|copia|copiar)\s+"
        r"(?:(?:el|la)\s+)?(?:archivo|fichero)\s+"
        r"(.+?)\s+(?:de|desde|en)\s+(?:(?:la|el)\s+)?"
        +LOC+r"\s+(?:a|al|hacia)\s+(?:(?:el|la|mi)\s+)?"+LOC)
    m=re.fullmatch(named,t)
    if m:
        verb,name,src,dest=m.groups()
        if name:
            return "pc_transfer",{
                "operation":"copy" if verb in ("copia","copiar") else "move",
                "pick":"name","name":name.strip(),"from":_where(src),"to":_where(dest)
            }

    rename=(r"(?:renombra|renombrar|cambia el nombre de)\s+"
        r"(?:(?:el|la)\s+)?(?:archivo|carpeta)\s+"
        r"(.+?)\s+(?:de|en)\s+(?:(?:la|el)\s+)?"
        +LOC+r"\s+(?:a|por|como)\s+(.+)")
    m=re.fullmatch(rename,t)
    if m:
        old,loc,new=m.groups()
        return "pc_rename",{"old":old.strip(),"location":_where(loc),"new":new.strip()}

    create=(r"(?:crea|crear|creame|genera)\s+"
        r"(?:(?:una|un)\s+)?(?:(?:nueva|nuevo)\s+)?"
        r"(carpeta|subcarpeta|archivo de texto|txt)\s+"
        r"(?:llamad[oa]|con (?:el )?nombre de|de nombre)\s+"
        r"(.+?)\s+(?:en|dentro de)\s+(?:(?:el|la|mi)\s+)?"+LOC)
    m=re.fullmatch(create,t)
    if m:
        kind,name,loc=m.groups()
        return "pc_create",{
            "kind":"folder" if kind in ("carpeta","subcarpeta") else "text",
            "name":name.strip(),"location":_where(loc)
        }

    # Explicit append; never overwrite a document by voice.
    append=(r"(?:agrega|anade|escribe)\s+(?:(?:el )?texto\s+)?"
        r"(.+?)\s+(?:al|en el)\s+archivo\s+(.+?)\s+"
        r"(?:de|en)\s+(?:(?:el|la)\s+)?"+LOC)
    m=re.fullmatch(append,t)
    if m:
        text,name,loc=m.groups()
        return "pc_append",{
            "text":text.strip(),"name":name.strip(),"location":_where(loc)
        }

    return None

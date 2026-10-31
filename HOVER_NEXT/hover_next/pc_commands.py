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
    # Natural requests are normalized into the same bounded actions rather
    # than requiring users to memorize one fixed imperative phrase.
    t=re.sub(
        r"^(?:quiero|necesito)\s+que\s+(?:me\s+)?"
        r"(?:crees|creas|hagas|generes|prepares)\s+",
        "crea ",t)
    t=re.sub(r"^(?:hazme|haceme|preparame|prepara|construye)\s+","crea ",t)
    t=re.sub(
        r"^(?:me\s+)?(?:puedes|podrias)\s+"
        r"(?:hacer|crear|preparar)\s+",
        "crea ",t)
    # Polite imperatives must not be mistaken for Google questions.
    t=re.sub(r"^(?:oye|hey|por favor)[, ]+", "", t)
    t=re.sub(r"^(?:(?:me )?puedes|(?:me )?podrias|quiero que|necesito que)\s+", "", t)
    return t.strip()


def _where(t):
    return LOCATIONS[t]


def parse_pc_command(text: str):
    """Return (action,args) for a bounded file command, or None."""
    t=_clean(text)
    # Explicit foreground-window operations only. No killing processes or
    # accidentally closing arbitrary background/system applications.
    close = re.fullmatch(
        r"(?:cierra|cerrar|cierra(?:me)?|cerrame|termina)\s+"
        r"(?:(?:la|el|mi)\s+)?"
        r"(ventana actual|ventana activa|esta ventana|programa actual|"
        r"aplicacion actual|aplicacion activa|esto|"
        r"excel|word|powerpoint|power point|calculadora|"
        r"bloc de notas|notepad|paint|explorador(?: de archivos)?)",
        t)
    if close:
        name=close.group(1)
        aliases={
            "excel":"excel","word":"word","powerpoint":"powerpoint",
            "power point":"powerpoint","calculadora":"calculator",
            "bloc de notas":"notepad","notepad":"notepad",
            "paint":"paint","explorador":"explorer",
            "explorador de archivos":"explorer",
        }
        return "pc_close_window", {"app":aliases.get(name,"foreground")}

    # If a user omits the name, ask for it in the next voice turn instead
    # of creating a file with a guessed name such as "en escritorio".
    unnamed=re.fullmatch(
        r"(?:crea|crear|creame|genera|haz)\s+"
        r"(?:(?:un|una)\s+)?(?:(?:nueva|nuevo)\s+)?"
        r"(carpeta|subcarpeta|excel|archivo excel|archivo de excel|"
        r"word|documento word|archivo de word|archivo word|"
        r"archivo de texto|txt|csv)"
        r"(?:\s+(?:en|dentro de)\s+(?:(?:el|la|mi)\s+)?"
        r"(?:carpeta de\s+)?"+LOC+r")?",
        t)
    if unnamed:
        kind,where=unnamed.groups()
        # Preserve HOVER's existing favorite-folder workflows when a user
        # says "crea una subcarpeta" or "crea un TXT" without a location.
        # Those routes ask for a name and use the configured favorite.
        if ((kind in ("subcarpeta","txt","archivo de texto") and not where)
                or (kind in ("txt","archivo de texto") and
                    where=="carpeta favorita")):
            return None
        aliases={"carpeta":"folder","subcarpeta":"folder",
                 "excel":"excel","archivo excel":"excel",
                 "archivo de excel":"excel",
                 "word":"word","documento word":"word",
                 "archivo de word":"word","archivo word":"word",
                 "archivo de texto":"txt","txt":"txt","csv":"csv"}
        return "pc_name_needed",{
            "kind":aliases[kind],
            "location":_where(where) if where else "desktop",
        }

    # Create an actual saved file, not just a new unsaved Office window.
    # Missing location defaults to the user's Desktop; never system paths.
    # Requiring a recognizable kind + name avoids treating general questions
    # or ambiguous ASR fragments as file-system mutations.
    creation = re.fullmatch(
        r"(?:crea|crear|creame|genera|generar|haz|hacer)\s+"
        r"(?:(?:un|una)\s+)?(?:(?:nueva|nuevo)\s+)?"
        r"(carpeta|subcarpeta|archivo de texto|archivo de excel|"
        r"archivo excel|archivo de word|archivo word|"
        r"documento de word|documento word|archivo csv|"
        r"archivo txt|txt|excel|word|xlsx|docx|csv|"
        r"hoja de calculo|libro de excel|documento de texto)\s+"
        r"(?:(?:que\s+se\s+llam[ae]|llamad[oa]|"
        r"con\s+(?:el\s+)?nombre(?:\s+de)?|de\s+nombre)\s+)?"
        r"(.+?)"
        r"(?:\s+(?:en|dentro\s+de)\s+(?:(?:el|la|mi)\s+)?"
        r"(?:carpeta\s+de\s+)?"+LOC+r")?",
        t)
    if creation:
        kind, name, where=creation.groups()
        if (not where and kind in (
                "subcarpeta","txt","archivo txt","archivo de texto",
                "documento de texto")):
            return None
        kind_map={
            "carpeta":"folder","subcarpeta":"folder",
            "archivo de texto":"text","documento de texto":"text",
            "archivo txt":"text","txt":"text",
            "excel":"excel","archivo de excel":"excel",
            "archivo excel":"excel","xlsx":"excel",
            "hoja de calculo":"excel","libro de excel":"excel",
            "word":"word","archivo de word":"word",
            "archivo word":"word","documento word":"word",
            "documento de word":"word","docx":"word",
            "csv":"csv","archivo csv":"csv",
        }
        # Slashes, drive letters, wildcards and executable suffixes are
        # rejected by the storage layer as an additional invariant.
        name=name.strip(" .,")
        if name and len(name)<=100:
            return "pc_create",{
                "kind":kind_map[kind],"name":name,
                "location":_where(where) if where else "desktop"
            }

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

    # Whisper transcribes an imperative as "que elimina..." occasionally.
    # This narrow grammar is for the LAST file HOVER actually moved, not
    # the newest file on the target folder. Never guess based on timestamps.
    moved=(r"(?:que\s+)?(?:elimina|eliminar|borra|borrar)\s+"
           r"(?:el\s+)?(?:ultimo|ultima)\s+(?:archivo|fichero|documento)\s+"
           r"(?:que\s+)?(?:movido|movida|moviste|trasladado|trasladada)\s+"
           r"(?:a|al|hacia)\s+(?:(?:el|la|mi)\s+)?"+LOC)
    m=re.fullmatch(moved,t)
    if m:
        return "pc_delete",{"pick":"last_moved","location":_where(m.group(1))}

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

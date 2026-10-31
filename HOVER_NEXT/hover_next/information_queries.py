"""Route spoken information requests to Google, without affecting desktop actions.

Read-only browser requests only. A question about creating/deleting things
must be a *search*, not a filesystem, GitHub or purchase instruction.
The caller strips the HOVER wake word before invoking this module.
"""
from __future__ import annotations

import re
import unicodedata


def _plain(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(c)
    )


_LANGUAGES = {
    "ingles": "en", "english": "en", "espanol": "es",
    "castellano": "es", "frances": "fr", "aleman": "de",
    "portugues": "pt", "italiano": "it", "japones": "ja",
    "chino": "zh-CN", "coreano": "ko", "ruso": "ru",
}

# These phrases are interpreted only at the START of the user's command;
# matching them inside a message to ChatGPT would hijack that message.
_SEARCH_PREFIX = re.compile(
    r"^(?:busca(?:me)?|buscar|busqueda(?:\s+de)?|"
    r"investiga|investigar|encuentra|encontrar|"
    r"consulta|consultar|averigua|averiguar|"
    r"googlea|googlear|buscame\s+informacion\s+sobre)"
    r"\s+(.+)$"
)

_QUESTION_PREFIX = re.compile(
    r"^(?:que\s+(?:es|son|significa|quiere\s+decir|pasa|ocurre|"
    r"debo|puedo|podria|diferencia\s+hay|relacion\s+hay)|"
    r"quien(?:es)?\b|"
    r"cual(?:es)?\s+(?:es|son|sera|seria|tiene|tienen)|"
    r"como(?:\s+se|\s+puedo|\s+hago|\s+funciona|\s+abrir|\s+crear|\s+)?|"
    r"por\s+que|para\s+que|de\s+que|"
    r"cuando|donde|a\s+donde|"
    r"cuant[oa]s?(?:\s+|$)|"
    r"es\s+posible|se\s+puede|puedo|puedes|podrias|"
    r"cual\s+es\s+la\s+diferencia|"
    r"hay\s+alguna|existe|"
    r"en\s+que\s+se\s+diferencia)\b"
)

_EXPLANATION_PREFIX = re.compile(
    r"^(?:diferencia(?:s)?\s+entre|"
    r"compar(?:a|ar|ame|acion)(?:\s+(?:entre|de))?|"
    r"explica(?:me)?(?:\s+la)?\s+diferencia(?:s)?|"
    r"dime\s+(?:la\s+diferencia|que\s+es|como|cual)|"
    r"definicion\s+de|significado\s+de|"
    r"explica(?:me)?\s+(?:que|como|por\s+que)|"
    r"informacion\s+sobre|"
    r"quiero\s+saber|"
    r"necesito\s+saber)\b"
)

_TRANSLATE_PREFIX = re.compile(
    r"^(?:traduce(?:me)?|traducir|traduccion\s+de|"
    r"traduceme|como\s+se\s+dice)\b"
)



def remove_wake_preserving_text(text: str) -> str | None:
    """Strip a recognized wake prefix without removing C++, ñ or punctuation.

    This is used only after HOVER's conservative wake detector accepts the
    input. Otherwise no wake is implied by this helper alone.
    """
    match = re.match(
        r"^\s*(?:(?:oye|oie|oi|hey|hola|huji|uji|huyi)"
        r"[\s,.;:¿¡!?]*)?"
        r"(?:hover|jover|over|llover|hober|huver|hoguer)\b"
        r"[\s,.;:¿¡!?]*",
        text, re.IGNORECASE,
    )
    return text[match.end():].strip() if match else None


def information_request(utterance: str) -> tuple[str, dict[str, str]] | None:
    """Return a safe search/translation intent for a standalone utterance.

    Keep the query's original symbols (e.g. C++) and accents; strip only
    trailing sentence punctuation. Never execute arbitrary text as a command.
    """
    utterance = " ".join(utterance.strip().split())
    if not utterance:
        return None
    plain = _plain(utterance).strip(" \t.!?¿¡")
    original = utterance.strip(" \t.!?¿¡")
    if not plain:
        return None
    if _TRANSLATE_PREFIX.match(plain):
        # Extract the text from the original, preserving non-ASCII symbols.
        translation_prefix = _TRANSLATE_PREFIX.match(plain)
        payload = original[translation_prefix.end():].strip(" :;,")
        # The user explicitly chooses the target language when present.
        # No target -> Google Translate defaults to English for Spanish speech.
        target = "en"
        target_match = re.search(
            r"\s+(?:a|al|hacia|en)\s+(?:el\s+idioma\s+)?"
            r"(ingles|english|espanol|castellano|frances|aleman|"
            r"portugues|italiano|japones|chino|coreano|ruso)$",
            _plain(payload),
        )
        if target_match:
            target = _LANGUAGES[target_match.group(1)]
            payload = payload[:target_match.start()].strip(" :;,")
        return "google_translate", {"text": payload, "target": target}

    explicit = _SEARCH_PREFIX.match(plain)
    if explicit:
        # Extract after first initial verb, keeping C++, ñ and accents.
        content = original[explicit.start(1):].strip()
        # A garbled "busca y ... busca and Google" is not a clear query.
        if content.casefold().startswith(("y ", "and ")):
            return None
        content = re.sub(
            r"^(?:en|por)\s+(?:google|internet|la web)\s+",
            "", content, flags=re.IGNORECASE
        )
        content = re.sub(
            r"\s+(?:en|por)\s+(?:google|internet|la web)$",
            "", content, flags=re.IGNORECASE
        ).strip(" \t,.!?¿¡")
        if len(content) >= 2:
            return "google_search", {"query": content.casefold()}
        return "search_query_needed", {}

    if _QUESTION_PREFIX.match(plain) or _EXPLANATION_PREFIX.match(plain):
        return "google_search", {"query": original}

    # The recognition engine sometimes supplies only a question mark.
    # Route true spoken questions to Google unless they explicitly begin
    # with an application/action instruction (handled by caller).
    if utterance.rstrip().endswith("?") and re.match(
        r"^(?:me\s+puedes|podrias|podr[ií]as|sabes|"
        r"me\s+explicas|me\s+dices|tienes\s+idea)\b",
        _plain(original),
    ):
        return "google_search", {"query": original}
    return None

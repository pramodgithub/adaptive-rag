import unicodedata


BIDI_FORMATTING_CHARS = {
    "\u202a",  # LEFT-TO-RIGHT EMBEDDING
    "\u202b",  # RIGHT-TO-LEFT EMBEDDING
    "\u202c",  # POP DIRECTIONAL FORMATTING
    "\u202d",  # LEFT-TO-RIGHT OVERRIDE
    "\u202e",  # RIGHT-TO-LEFT OVERRIDE
    "\u2066",  # LEFT-TO-RIGHT ISOLATE
    "\u2067",  # RIGHT-TO-LEFT ISOLATE
    "\u2068",  # FIRST STRONG ISOLATE
    "\u2069",  # POP DIRECTIONAL ISOLATE
}


def normalize_text(text: str) -> str:
    if not text:
        return text

    text = unicodedata.normalize("NFKC", text)

    return "".join(
        char for char in text
        if char not in BIDI_FORMATTING_CHARS
    )

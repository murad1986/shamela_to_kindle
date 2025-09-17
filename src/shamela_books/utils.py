from __future__ import annotations

import html
import unicodedata as ud

# Bidirectional control characters and BOM/Tatweel handling
BIDI_CTRL = {
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
}

_AR_DIGITS = str.maketrans({
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})


def ar_digits_to_ascii(s: str) -> str:
    return s.translate(_AR_DIGITS)


def norm_ar_text(s: str) -> str:
    """Normalize Arabic text for display while preserving diacritics.
    - Decode entities
    - Remove bidi control/tatweel/soft hyphen
    - NFKC normalize
    - Collapse whitespace
    """
    if not s:
        return s
    s = html.unescape(s)
    s = s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u00AD", "")
    s = "".join(ch for ch in s if ch not in BIDI_CTRL)
    s = s.replace("\u0640", "")  # tatweel
    s = ud.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip()


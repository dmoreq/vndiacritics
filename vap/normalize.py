"""Vietnamese text normalization: accent stripping and NFC folding."""

from __future__ import annotations

import unicodedata

_D_STROKE = str.maketrans({"đ": "d", "Đ": "D"})


def strip_accent(text: str) -> str:
    """Remove Vietnamese tone marks and đ/Đ, returning lowercase ASCII-ish text.

    Works for both NFC and NFD input. Đ/đ is handled explicitly because it is a
    distinct letter (U+0111), not a base letter plus a combining mark, so NFD will
    not decompose it.
    """
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.translate(_D_STROKE).lower()


def nfc(text: str) -> str:
    """Return NFC-normalized text."""
    return unicodedata.normalize("NFC", text)

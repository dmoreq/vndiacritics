"""Vietnamese diacritic restoration.

Public surface: `Model` for restoration, the two stripping helpers for preparing input.
Everything else is internal and may move between versions.
"""

from vndiacritics.model import Model
from vndiacritics.normalize import strip_accent, strip_accent_keep_case

__all__ = ["Model", "strip_accent", "strip_accent_keep_case"]

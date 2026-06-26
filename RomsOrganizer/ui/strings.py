"""Caricatore traduzioni (i18n). Niente pygame qui: solo lettura JSON.

t("chiave", n=3) -> stringa nella lingua attiva, con .format(...) per i segnaposto.
"""
from __future__ import annotations

import json
from pathlib import Path

_I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
_cache: dict[str, dict] = {}
_lang = "it"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if (_I18N_DIR / f"{lang}.json").is_file() else "it"


def current_lang() -> str:
    return _lang


def toggle_lang() -> str:
    set_lang("en" if _lang == "it" else "it")
    return _lang


def _table(lang: str) -> dict:
    if lang not in _cache:
        f = _I18N_DIR / f"{lang}.json"
        try:
            _cache[lang] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache[lang] = {}
    return _cache[lang]


def t(key: str, **kw) -> str:
    s = _table(_lang).get(key) or _table("it").get(key) or key
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError):
        return s

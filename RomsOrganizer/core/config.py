"""Configurazione e funzioni di normalizzazione del motore.

Qui stanno le 'manopole' del comportamento: dove sono le ROM, dove finisce il
backup, quali estensioni appartengono a quale sistema, e le regex che ripuliscono
i nomi. Centralizzarle qui evita numeri/stringhe magiche sparse nel codice.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# --- Percorsi -------------------------------------------------------------
# Su Batocera le ROM stanno in /userdata/roms. Si puo' sovrascrivere con la
# variabile d'ambiente ROMSORG_ROMS_DIR (comodissimo per i test in locale).
DEFAULT_ROMS_DIR = "/userdata/roms"
BACKUP_DIR_NAME = "ROM eliminate"            # come richiesto: cartella in chiaro
MANIFEST_NAME = ".romsorganizer_manifest.json"  # registro per il ripristino


def roms_dir() -> Path:
    return Path(os.environ.get("ROMSORG_ROMS_DIR", DEFAULT_ROMS_DIR))


def backup_dir() -> Path:
    # Il backup vive DENTRO roms cosi' l'utente lo trova subito, ma il nome con
    # spazio non e' un sistema valido: EmulationStation lo ignora nelle liste.
    return roms_dir() / BACKUP_DIR_NAME


def manifest_path() -> Path:
    return backup_dir() / MANIFEST_NAME


# Config/salvataggi: come RGSX, fuori dalle ROM, in /userdata/saves.
DEFAULT_SAVES_DIR = "/userdata/saves/ports/romsorganizer"


def saves_dir() -> Path:
    d = Path(os.environ.get("ROMSORG_SAVES_DIR", DEFAULT_SAVES_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return saves_dir() / "settings.json"


def controls_path() -> Path:
    return saves_dir() / "controls.json"


def load_settings() -> dict:
    import json
    p = settings_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"lang": "it"}


def save_settings(data: dict) -> None:
    import json
    settings_path().write_text(json.dumps(data, indent=2, ensure_ascii=False),
                               encoding="utf-8")


# Cartelle dentro /userdata/roms che NON sono sistemi di gioco: vanno saltate
# durante la scansione per non trattarle come ROM.
SKIP_DIRS = {BACKUP_DIR_NAME, "ports", "tools", "favorites", "images", "media"}

# --- Formati disco --------------------------------------------------------
# Per il motore "stesso gioco, formati diversi": se per lo stesso gioco esistono
# sia un formato COMPRESSO sia uno NON compresso, suggeriamo di tenere il
# compresso (occupa meno e Batocera lo legge nativamente).
DISC_COMPRESSED = {"chd", "rvz", "cso", "pbp", "wbfs"}
DISC_UNCOMPRESSED = {"iso", "cue", "bin", "gdi", "img", "mdf"}
# .bin/.cue sono una COPPIA, non duplicati fra loro: non vanno mai separati.
PAIRED_EXTS = {"cue", "bin", "ccd", "sub"}

# --- Mappa estensione -> sistema atteso (per "ROM nel sistema giusto") -----
# Solo estensioni NON ambigue. Le estensioni generiche (zip, 7z, iso, chd, bin...)
# appartengono a troppi sistemi: spostarle alla cieca e' pericoloso, quindi le
# escludiamo di proposito. Meglio non toccare che sbagliare.
EXT_TO_SYSTEM = {
    "nes": "nes", "fds": "fds",
    "sfc": "snes", "smc": "snes",
    "gb": "gb", "gbc": "gbc", "gba": "gba",
    "n64": "n64", "z64": "n64", "v64": "n64",
    "md": "megadrive", "smd": "megadrive", "gen": "megadrive",
    "sms": "mastersystem", "gg": "gamegear",
    "pce": "pcengine", "a78": "atari7800", "a26": "atari2600",
    "lnx": "atarilynx", "ws": "wonderswan", "wsc": "wonderswancolor",
    "ngp": "ngp", "ngc": "ngpc", "32x": "sega32x",
    "nds": "nds", "3ds": "n3ds", "vb": "virtualboy",
}

# --- Regex per ripulire i nomi -------------------------------------------
# Tutti i tag fra parentesi tonde o quadre: (USA), (Europe), (Rev 1), [!], [b]...
TAG_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# Suffisso di copia in coda al nome: " (1)", " [2]", " - Copia", " copy".
COPY_SUFFIX_RE = re.compile(r"\s*(?:\(\d+\)|\[\d+\]|-?\s*cop(?:y|ia))\s*$", re.IGNORECASE)


def strip_all_tags(stem: str) -> str:
    """Nome senza NESSUN tag: per capire se due ROM sono lo stesso gioco
    a prescindere da regione/revisione. 'Sonic (USA) (Rev 1)' -> 'sonic'."""
    return TAG_RE.sub("", stem).strip().lower()


def strip_copy_suffix(stem: str) -> str:
    """Nome senza il solo suffisso di copia, mantenendo i tag regione.
    'Sonic (USA) (1)' -> 'sonic (usa)'. Applicata in loop per copie multiple."""
    prev = None
    s = stem.strip()
    while prev != s:
        prev = s
        s = COPY_SUFFIX_RE.sub("", s).strip()
    return s.lower()


def display_clean_name(stem: str) -> str:
    """Nome 'bello' per le liste: tolti i tag, ma con le maiuscole originali.
    Usato dal riordino per pulire i <name> nel gamelist."""
    return TAG_RE.sub("", stem).strip()


def human_size(n: int) -> str:
    """Byte -> stringa leggibile (1.5 MB)."""
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.0f} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"

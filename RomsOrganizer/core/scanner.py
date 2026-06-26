"""Scansione del disco: trova tutte le ROM e i gamelist.

Output: un dizionario {sistema: [RomFile, ...]}. Volutamente 'stupido' e veloce:
non decide nulla, raccoglie solo i fatti. Le decisioni le prende dedup.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from . import config
from .models import RomFile

# Estensioni che NON sono ROM: artwork, metadati, testi. Da ignorare nello scan.
NON_ROM_EXTS = {
    "xml", "txt", "nfo", "dat", "png", "jpg", "jpeg", "gif", "mp4", "json",
    "cfg", "ini", "log", "srm", "state", "sav", "db", "md5", "sha1", "aup",
}


def scan_systems(roms: Path | None = None) -> Dict[str, List[RomFile]]:
    """Ritorna {sistema: lista di RomFile} per ogni cartella-sistema valida."""
    base = roms or config.roms_dir()
    result: Dict[str, List[RomFile]] = {}
    if not base.is_dir():
        return result

    for system_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if system_dir.name in config.SKIP_DIRS:
            continue
        files: List[RomFile] = []
        # rglob cattura anche ROM in sottocartelle (es. arcade con sottodir)
        for f in system_dir.rglob("*"):
            if not f.is_file():
                continue
            ext = f.suffix.lower().lstrip(".")
            if not ext or ext in NON_ROM_EXTS:
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            files.append(RomFile(path=f, system=system_dir.name, size=size))
        if files:
            result[system_dir.name] = files
    return result


def find_gamelists(roms: Path | None = None) -> Dict[str, Path]:
    """Ritorna {sistema: percorso gamelist.xml} per i gamelist esistenti."""
    base = roms or config.roms_dir()
    out: Dict[str, Path] = {}
    if not base.is_dir():
        return out
    for system_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if system_dir.name in config.SKIP_DIRS:
            continue
        gl = system_dir / "gamelist.xml"
        if gl.is_file():
            out[system_dir.name] = gl
    return out

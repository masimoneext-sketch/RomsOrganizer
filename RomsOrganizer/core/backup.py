"""Backup e ripristino: il paracadute del tool.

Regola d'oro: NON si cancella mai. I file 'rimossi' vengono SPOSTATI nella
cartella 'ROM eliminate' e ogni spostamento e' registrato in un manifest JSON.
Da quel registro la funzione restore() rimette tutto esattamente dov'era.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Dict, List

from . import config
from .models import RomFile


def _load_manifest() -> List[dict]:
    mp = config.manifest_path()
    if not mp.is_file():
        return []
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_manifest(entries: List[dict]) -> None:
    mp = config.manifest_path()
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _unique_dest(dest: Path) -> Path:
    """Evita di sovrascrivere un file gia' presente nel backup."""
    if not dest.exists():
        return dest
    i = 1
    while True:
        cand = dest.with_name(f"{dest.stem}__{i}{dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _entry_for(path: Path, system: str, reason: str, size: int) -> dict:
    dest = _unique_dest(config.backup_dir() / system / path.name)
    return {
        "orig": str(path),
        "backup": str(dest),
        "system": system,
        "name": path.name,
        "reason": reason,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "size": size,
    }


def move_to_backup(rf: RomFile, reason: str, dry_run: bool = False) -> dict:
    """Sposta una ROM nel backup e restituisce la voce di manifest della scheda.

    Se la ROM e' una scheda cue-set (.cue/.ccd), le sue tracce dati vengono
    spostate INSIEME (e registrate nel manifest), cosi' l'unita' non si spezza e
    il ripristino le rimette tutte. Con dry_run=True non tocca il disco.
    """
    entry = _entry_for(rf.path, rf.system, reason, rf.size)
    # Tracce dati della scheda (vuoto se non e' un cue-set).
    members: list[Path] = []
    if rf.ext in config.CUESHEET_EXTS:
        members = config.cue_member_paths(rf.path)
    if dry_run:
        return entry
    extra: List[dict] = []
    for m in members:
        try:
            extra.append(_entry_for(m, rf.system, reason, m.stat().st_size))
        except OSError:
            pass
    # Sposta prima le tracce, poi la scheda: se qualcosa va storto, almeno la
    # scheda resta al suo posto a indicare il set ancora presente.
    moved: List[dict] = []
    for e in extra:
        Path(e["backup"]).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(e["orig"], e["backup"])
        moved.append(e)
    Path(entry["backup"]).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(rf.path), entry["backup"])
    moved.append(entry)
    entries = _load_manifest()
    entries.extend(moved)
    _save_manifest(entries)
    return entry


def list_backup() -> List[dict]:
    """Voci attualmente in backup (per la schermata Ripristina)."""
    return _load_manifest()


def restore(entry: dict, dry_run: bool = False) -> bool:
    """Rimette una ROM dal backup alla posizione originale. True se riuscito."""
    src = Path(entry["backup"])
    dst = Path(entry["orig"])
    if dry_run:
        return src.exists()
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Se nel frattempo qualcosa ha rioccupato il percorso originale, NON lo
    # sovrascriviamo: il file ripristinato atterra con un nome unico accanto
    # (stessa cautela di move_to_backup). Cosi' il ripristino non distrugge dati.
    dst = _unique_dest(dst)
    shutil.move(str(src), str(dst))
    entries = [e for e in _load_manifest() if e.get("backup") != entry["backup"]]
    _save_manifest(entries)
    return True


def restore_all(dry_run: bool = False) -> int:
    """Ripristina tutto il backup. Ritorna quanti file sono stati rimessi."""
    done = 0
    for entry in list(list_backup()):
        if restore(entry, dry_run=dry_run):
            done += 1
    return done


def backup_summary() -> Dict[str, int]:
    """Riepilogo veloce: quante voci e quanto spazio occupano."""
    entries = _load_manifest()
    return {
        "count": len(entries),
        "bytes": sum(int(e.get("size", 0)) for e in entries),
    }

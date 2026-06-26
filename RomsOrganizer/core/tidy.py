"""Riordino: le tre funzioni di 'messa in ordine' scelte.

1) Pulire i nomi mostrati (gamelist <name>) senza rinominare i file fisici.
2) Spostare le ROM finite nel sistema sbagliato in quello giusto.
3) Sistemare il gamelist.xml: togliere voci orfane/doppie e ordinare alfabeticamente.

Come per dedup, ogni funzione ha la modalita' dry_run per l'anteprima.
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

from . import config
from .models import RomFile


# 1) PULIRE I NOMI MOSTRATI ------------------------------------------------
def clean_display_names(gamelists: Dict[str, Path], dry_run: bool = False) -> List[dict]:
    """Toglie i tag dai <name> nel gamelist. I FILE non vengono rinominati."""
    changes: List[dict] = []
    for system, gl in gamelists.items():
        try:
            tree = ET.parse(gl)
        except ET.ParseError:
            continue
        root = tree.getroot()
        dirty = False
        for game in root.findall("game"):
            name_el = game.find("name")
            if name_el is None or not name_el.text:
                continue
            old = name_el.text.strip()
            new = config.display_clean_name(old)
            if new and new != old:
                changes.append({"system": system, "old": old, "new": new})
                if not dry_run:
                    name_el.text = new
                    dirty = True
        if dirty and not dry_run:
            tree.write(gl, encoding="utf-8", xml_declaration=True)
    return changes


# 2) ROM NEL SISTEMA GIUSTO ------------------------------------------------
def find_misplaced(systems: Dict[str, List[RomFile]]) -> List[dict]:
    """ROM la cui estensione (NON ambigua) indica un sistema diverso da quello in cui sta."""
    out: List[dict] = []
    for system, files in systems.items():
        for rf in files:
            expected = config.EXT_TO_SYSTEM.get(rf.ext)
            if expected and expected != system:
                out.append({"rom": rf, "from": system, "to": expected})
    return out


def fix_misplaced(item: dict, dry_run: bool = False) -> bool:
    """Sposta una ROM nel sistema corretto. Crea la cartella destinazione se manca."""
    rf: RomFile = item["rom"]
    dest_dir = config.roms_dir() / item["to"]
    dest = dest_dir / rf.path.name
    if dest.exists():          # gia' presente di la': non sovrascrivo, salto
        return False
    if dry_run:
        return True
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(rf.path), str(dest))
    return True


# 3) SISTEMARE IL GAMELIST -------------------------------------------------
def tidy_gamelist(gl: Path, dry_run: bool = False) -> dict:
    """Rimuove dal gamelist le voci orfane e doppie, poi ordina per <name>.

    Ritorna un conteggio di cosa e' stato (o sarebbe) cambiato.
    """
    res = {"removed_orphan": 0, "removed_dup": 0, "reordered": False}
    try:
        tree = ET.parse(gl)
    except ET.ParseError:
        return res
    root = tree.getroot()
    games = root.findall("game")

    keep: List[ET.Element] = []
    seen: set[str] = set()
    for game in games:
        pv = (game.findtext("path") or "").strip()
        if not pv:
            continue
        if pv in seen:
            res["removed_dup"] += 1
            continue
        target = (gl.parent / pv).resolve()
        if not target.exists():
            res["removed_orphan"] += 1
            continue
        seen.add(pv)
        keep.append(game)

    ordered = sorted(keep, key=lambda g: (g.findtext("name") or "").lower())
    res["reordered"] = ordered != keep

    if not dry_run and (res["removed_orphan"] or res["removed_dup"] or res["reordered"]):
        for g in games:
            root.remove(g)
        for g in ordered:
            root.append(g)
        tree.write(gl, encoding="utf-8", xml_declaration=True)
    return res

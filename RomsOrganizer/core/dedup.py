"""I quattro motori anti-duplicato.

Ognuno riceve i dati grezzi dello scanner e restituisce una lista di gruppi da
proporre all'utente. Nessuno cancella nulla: il motore PROPONE, l'utente sceglie,
backup.py esegue. Questa separazione e' cio' che rende il tool sicuro.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from . import config
from .models import (
    DuplicateGroup, GamelistIssue, RomFile,
    KIND_SAME_NAME, KIND_FORMAT, KIND_REGION,
)


# 1) STESSO NOME -----------------------------------------------------------
def find_same_name(systems: Dict[str, List[RomFile]]) -> List[DuplicateGroup]:
    """File doppi: 'Game.zip' + 'Game (1).zip', o stessa ROM copiata piu' volte.

    Chiave di raggruppamento = nome senza suffisso di copia, MA con i tag regione
    intatti (cosi' due regioni diverse NON cadono qui: sono affare del motore 1G1R).
    """
    groups: List[DuplicateGroup] = []
    for system, files in systems.items():
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in files:
            key = f"{config.strip_copy_suffix(rf.stem)}.{rf.ext}"
            buckets[key].append(rf)
        for key, rfs in buckets.items():
            if len(rfs) < 2:
                continue
            # Tieni il nome 'pulito' (piu' corto = senza '(1)'): di solito l'originale.
            rfs_sorted = sorted(rfs, key=lambda r: (len(r.name), r.name))
            groups.append(DuplicateGroup(
                kind=KIND_SAME_NAME, system=system,
                base=rfs_sorted[0].stem, candidates=rfs_sorted, keep_index=0,
            ))
    return groups


# 2) FORMATI DIVERSI -------------------------------------------------------
def _format_unit_key(rf: RomFile) -> str:
    """Nome-base (senza tag) per accomunare formati dello stesso gioco."""
    return config.strip_all_tags(rf.stem)


def find_format_variants(systems: Dict[str, List[RomFile]]) -> List[DuplicateGroup]:
    """Stesso gioco presente sia compresso (.chd) sia non compresso (.cue/.bin/.iso).

    Le coppie .cue+.bin vengono trattate come UN'unita' 'cue-set' e mai separate.
    Suggerimento: tieni il compresso.
    """
    groups: List[DuplicateGroup] = []
    for system, files in systems.items():
        # Consideriamo solo i file che sono formati-disco rilevanti.
        disc = [f for f in files
                if f.ext in config.DISC_COMPRESSED or f.ext in config.DISC_UNCOMPRESSED]
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in disc:
            buckets[_format_unit_key(rf)].append(rf)

        for base, rfs in buckets.items():
            exts = {r.ext for r in rfs}
            has_compressed = exts & config.DISC_COMPRESSED
            has_uncompressed = exts & config.DISC_UNCOMPRESSED
            # Ci interessa solo se coesistono i due mondi (compresso vs no).
            if not (has_compressed and has_uncompressed):
                continue
            # Suggeriamo di tenere il primo formato compresso trovato.
            keep = next(i for i, r in enumerate(rfs) if r.ext in config.DISC_COMPRESSED)
            groups.append(DuplicateGroup(
                kind=KIND_FORMAT, system=system, base=base,
                candidates=rfs, keep_index=keep,
            ))
    return groups


# 3) VOCI DOPPIE / ORFANE NEL GAMELIST ------------------------------------
def find_gamelist_issues(gamelists: Dict[str, Path]) -> List[GamelistIssue]:
    """Voci <game> con lo stesso <path> (doppie) o che puntano a file mancanti (orfane)."""
    issues: List[GamelistIssue] = []
    for system, gl in gamelists.items():
        try:
            root = ET.parse(gl).getroot()
        except ET.ParseError:
            continue
        seen: set[str] = set()
        for game in root.findall("game"):
            path_el = game.find("path")
            if path_el is None or not path_el.text:
                continue
            pv = path_el.text.strip()
            name = (game.findtext("name") or pv).strip()
            # voce doppia
            if pv in seen:
                issues.append(GamelistIssue(system, gl, "duplicate_entry", pv, name))
                continue
            seen.add(pv)
            # voce orfana: il file referenziato non esiste piu'
            target = (gl.parent / pv).resolve()
            if not target.exists():
                issues.append(GamelistIssue(system, gl, "orphan_entry", pv, name))
    return issues


# 4) REGIONI / REVISIONI (1G1R) -------------------------------------------
def find_region_variants(systems: Dict[str, List[RomFile]]) -> List[DuplicateGroup]:
    """Stesso gioco in piu' regioni/revisioni: 'Mario (Japan)' + 'Mario (Germany)'.

    Raggruppa per nome senza tag e segnala solo se i candidati differiscono
    davvero per tag (almeno due nomi-file distinti). Scelta sempre manuale.
    """
    groups: List[DuplicateGroup] = []
    for system, files in systems.items():
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in files:
            buckets[config.strip_all_tags(rf.stem)].append(rf)
        for base, rfs in buckets.items():
            # Confronto al netto del suffisso di copia: 'Game' e 'Game (1)' hanno
            # lo stesso nome -> sono copie (affare di find_same_name), non regioni.
            distinct_names = {config.strip_copy_suffix(r.stem) for r in rfs}
            if len(rfs) < 2 or len(distinct_names) < 2:
                continue
            rfs_sorted = sorted(rfs, key=lambda r: r.name)
            # Suggerimento automatico: tieni la regione con priorita' piu' alta
            # (Europe > USA > World ...). Resta sempre modificabile a mano.
            keep = min(range(len(rfs_sorted)),
                       key=lambda i: config.region_rank(rfs_sorted[i].stem))
            groups.append(DuplicateGroup(
                kind=KIND_REGION, system=system, base=base,
                candidates=rfs_sorted, keep_index=keep,
            ))
    return groups

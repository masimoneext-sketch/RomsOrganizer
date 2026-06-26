"""I quattro motori anti-duplicato.

Ognuno riceve i dati grezzi dello scanner e restituisce una lista di gruppi da
proporre all'utente. Nessuno cancella nulla: il motore PROPONE, l'utente sceglie,
backup.py esegue. Questa separazione e' cio' che rende il tool sicuro.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from . import config
from .models import (
    DuplicateGroup, GamelistIssue, RomFile,
    KIND_SAME_NAME, KIND_FORMAT, KIND_REGION, KIND_EXACT,
)


# --- Cue-set: tracce che appartengono a una scheda (.cue/.ccd) -------------
# Le tracce (.bin/.img/.sub) NON sono giochi a se': vivono solo insieme alla
# loro scheda. I motori anti-duplicato non devono mai sceglierle/spostarle da
# sole, altrimenti orfanano la scheda. Qui calcoliamo, per ogni sistema, l'insieme
# dei percorsi-traccia da escludere dai candidati. backup.move_to_backup poi le
# sposta insieme alla scheda. (Nota: un .bin "sciolto", senza scheda, resta un
# gioco valido - es. Mega Drive - e NON viene escluso.)
def _cueset_member_paths(files: List[RomFile]) -> set:
    members: set = set()
    for rf in files:
        if rf.ext in config.CUESHEET_EXTS:
            members.update(config.cue_member_paths(rf.path))
    return members


# 1) STESSO NOME -----------------------------------------------------------
def find_same_name(systems: Dict[str, List[RomFile]]) -> List[DuplicateGroup]:
    """File doppi: 'Game.zip' + 'Game (1).zip', o stessa ROM copiata piu' volte.

    Chiave di raggruppamento = nome senza suffisso di copia, MA con i tag regione
    intatti (cosi' due regioni diverse NON cadono qui: sono affare del motore 1G1R).
    """
    groups: List[DuplicateGroup] = []
    for system, files in systems.items():
        members = _cueset_member_paths(files)
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in files:
            if rf.path in members:
                continue
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
    """Nome-base (senza tag) + disco, per accomunare i formati dello STESSO pezzo.

    Includere il disco evita di fondere 'Game (Disc 1)' e 'Game (Disc 2)': sono
    pezzi diversi dello stesso gioco, non due formati dell'identico contenuto."""
    return f"{config.strip_all_tags(rf.stem)}|{config.disc_token(rf.stem)}"


def find_format_variants(systems: Dict[str, List[RomFile]]) -> List[DuplicateGroup]:
    """Stesso gioco presente sia compresso (.chd) sia non compresso (.cue/.iso).

    Le tracce dati (.bin/.img/.sub) sono escluse: rappresentano gia' la scheda
    .cue/.ccd, che viaggia con loro. Suggerimento: tieni il compresso.
    """
    groups: List[DuplicateGroup] = []
    for system, files in systems.items():
        members = _cueset_member_paths(files)
        # Solo formati-disco rilevanti, e mai una traccia di un cue-set da sola.
        disc = [f for f in files
                if (f.ext in config.DISC_COMPRESSED or f.ext in config.DISC_UNCOMPRESSED)
                and f.path not in members]
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in disc:
            buckets[_format_unit_key(rf)].append(rf)

        for rfs in buckets.values():
            exts = {r.ext for r in rfs}
            has_compressed = exts & config.DISC_COMPRESSED
            has_uncompressed = exts & config.DISC_UNCOMPRESSED
            # Ci interessa solo se coesistono i due mondi (compresso vs no).
            if not (has_compressed and has_uncompressed):
                continue
            # Suggeriamo di tenere il primo formato compresso trovato.
            keep = next(i for i, r in enumerate(rfs) if r.ext in config.DISC_COMPRESSED)
            groups.append(DuplicateGroup(
                kind=KIND_FORMAT, system=system,
                base=config.strip_all_tags(rfs[0].stem),
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
        members = _cueset_member_paths(files)
        buckets: Dict[str, List[RomFile]] = defaultdict(list)
        for rf in files:
            if rf.path in members:
                continue
            # La chiave include il disco/traccia: 'Game (Disc 1)' e 'Game (Disc 2)'
            # NON finiscono nello stesso gruppo (sono pezzi, non regioni rivali).
            key = f"{config.strip_all_tags(rf.stem)}|{config.disc_token(rf.stem)}"
            buckets[key].append(rf)
        for rfs in buckets.values():
            # Confronto al netto del suffisso di copia: 'Game' e 'Game (1)' hanno
            # lo stesso nome -> sono copie (affare di find_same_name), non regioni.
            distinct_names = {config.strip_copy_suffix(r.stem) for r in rfs}
            if len(rfs) < 2 or len(distinct_names) < 2:
                continue
            rfs_sorted = sorted(rfs, key=lambda r: r.name)
            base = config.strip_all_tags(rfs_sorted[0].stem)
            # Suggerimento automatico: tieni la regione con priorita' piu' alta
            # (Europe > USA > World ...). Resta sempre modificabile a mano.
            keep = min(range(len(rfs_sorted)),
                       key=lambda i: config.region_rank(rfs_sorted[i].stem))
            groups.append(DuplicateGroup(
                kind=KIND_REGION, system=system, base=base,
                candidates=rfs_sorted, keep_index=keep,
            ))
    return groups


# 5) DUPLICATI ESATTI (contenuto identico, anche con nomi diversi) ----------
# Strategia: NON si hasha tutta la libreria. Due file identici hanno per forza
# la stessa dimensione, gia' nota gratis dallo scan. Si calcola l'hash SOLO sui
# file che condividono la dimensione con un altro (i candidati): pochi file,
# costo I/O minimo. L'hash completo sui candidati garantisce zero falsi positivi.
def find_exact_candidates(systems: Dict[str, List[RomFile]]) -> List[RomFile]:
    """File che condividono la dimensione con almeno un altro: vanno hashati.

    Le tracce dati di un cue-set sono escluse: tracce identiche (es. l'audio
    silenzioso comune a molti rip PSX) collidono fra giochi diversi, e spostarne
    una orfanerebbe la scheda. La scheda viaggia gia' con le sue tracce."""
    by_size: Dict[int, List[RomFile]] = defaultdict(list)
    for files in systems.values():
        members = _cueset_member_paths(files)
        for rf in files:
            if rf.size > 0 and rf.path not in members:
                by_size[rf.size].append(rf)
    candidates: List[RomFile] = []
    for rfs in by_size.values():
        if len(rfs) > 1:
            candidates.extend(rfs)
    return candidates


def hash_file(path: Path, chunk: int = 1 << 20) -> str:
    """MD5 del file letto a blocchi (1 MB), per non caricarlo tutto in RAM."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def group_exact(candidates: List[RomFile], hashes: Dict[str, str]) -> List[DuplicateGroup]:
    """Raggruppa i candidati per (dimensione, hash): contenuto identico garantito."""
    buckets: Dict[tuple, List[RomFile]] = defaultdict(list)
    for rf in candidates:
        h = hashes.get(str(rf.path))
        if h:
            buckets[(rf.size, h)].append(rf)
    groups: List[DuplicateGroup] = []
    for rfs in buckets.values():
        if len(rfs) < 2:
            continue
        # tieni il nome piu' pulito/corto; gli altri (anche in altri sistemi) in backup
        rfs_sorted = sorted(rfs, key=lambda r: (len(r.name), r.name))
        groups.append(DuplicateGroup(
            kind=KIND_EXACT, system=rfs_sorted[0].system,
            base=rfs_sorted[0].stem, candidates=rfs_sorted, keep_index=0,
        ))
    return groups

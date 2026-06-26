"""Modelli dati condivisi dal motore di RomsOrganizer.

Sono semplici "contenitori" (dataclass) senza logica: servono a far parlare
fra loro scanner -> dedup -> backup/tidy con strutture chiare invece di tuple
anonime. Tenerli qui, separati dalla UI, e' cio' che permette di testare il
motore senza pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class RomFile:
    """Un singolo file ROM trovato sul disco."""
    path: Path          # percorso assoluto del file
    system: str         # nome cartella sistema (es. "snes", "nes")
    size: int           # dimensione in byte (per riconoscere copie identiche)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def ext(self) -> str:
        # estensione minuscola senza punto (es. "zip", "chd")
        return self.path.suffix.lower().lstrip(".")


# Tipi di duplicato, usati come "etichetta" sui gruppi e nelle traduzioni.
KIND_SAME_NAME = "same_name"    # stesso gioco, file doppi (Game / Game (1))
KIND_FORMAT = "format"          # stesso gioco, formati diversi (.cue/.bin vs .chd)
KIND_REGION = "region"          # stesso gioco, regioni diverse (Japan vs Europe) -> 1G1R


@dataclass
class DuplicateGroup:
    """Un gruppo di file che il motore considera 'lo stesso gioco'.

    L'utente sceglie quale tenere (keep_index); tutti gli altri finiscono in
    backup. keep_index e' solo un SUGGERIMENTO pre-selezionato, mai imposto.
    """
    kind: str                       # KIND_SAME_NAME | KIND_FORMAT | KIND_REGION
    system: str                     # sistema di appartenenza
    base: str                       # nome-base normalizzato che li accomuna
    candidates: List[RomFile] = field(default_factory=list)
    keep_index: int = 0             # indice del candidato suggerito da tenere

    def to_remove(self, keep_index: int | None = None) -> List[RomFile]:
        """ROM da spostare in backup data una scelta (default: il suggerimento)."""
        k = self.keep_index if keep_index is None else keep_index
        return [c for i, c in enumerate(self.candidates) if i != k]


@dataclass
class GamelistIssue:
    """Problema rilevato dentro un gamelist.xml (non sui file ROM)."""
    system: str
    gamelist: Path
    kind: str            # "duplicate_entry" | "orphan_entry"
    path_value: str      # valore del campo <path> coinvolto
    name_value: str      # valore del campo <name> (per mostrarlo all'utente)

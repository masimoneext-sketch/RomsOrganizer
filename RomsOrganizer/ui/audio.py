"""Musica di sottofondo (opzionale, in loop) con interruttore ON/OFF.

Degrada con grazia: se manca il file musica o l'audio non e' disponibile sul
sistema, l'app funziona identica, solo senza musica. Lo stato ON/OFF si salva.
Il file atteso e' assets/music.ogg (preferito) o assets/music.mp3.
"""
from __future__ import annotations

from pathlib import Path

import pygame

from ..core import config

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_CANDIDATES = ("music.ogg", "music.mp3")
_VOLUME = 0.40


class Music:
    def __init__(self) -> None:
        self.available = False
        self.path: Path | None = None
        self.enabled = bool(config.load_settings().get("music", True))
        try:
            pygame.mixer.init()
        except pygame.error:
            return  # nessun audio sul sistema: si prosegue muti
        for name in _CANDIDATES:
            p = _ASSETS / name
            if p.is_file():
                self.path = p
                break
        if self.path:
            self._start()

    def _start(self) -> None:
        try:
            pygame.mixer.music.load(str(self.path))
            pygame.mixer.music.set_volume(_VOLUME if self.enabled else 0.0)
            pygame.mixer.music.play(-1)   # -1 = loop infinito
            self.available = True
        except pygame.error:
            self.available = False

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if self.available:
            pygame.mixer.music.set_volume(_VOLUME if self.enabled else 0.0)
        s = config.load_settings()
        s["music"] = self.enabled
        config.save_settings(s)
        return self.enabled

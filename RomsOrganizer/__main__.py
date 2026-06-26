"""Punto d'ingresso: `python3 -m RomsOrganizer`.

Tiene fuori pygame finche' non serve davvero, cosi' se manca diamo un messaggio
chiaro invece di un traceback. Il motore (core) resta usabile anche senza pygame.
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        import pygame  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "\n[RomsOrganizer] pygame non e' installato su questo sistema.\n"
            "Su Batocera di solito e' gia' presente. In caso contrario:\n"
            "  python3 -m pip install pygame\n\n")
        return 2

    from .ui import app
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

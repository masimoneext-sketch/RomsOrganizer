"""Registra RomsOrganizer nel menu PORTS con immagine di anteprima.

EmulationStation mostra l'artwork dei port leggendo /userdata/roms/ports/gamelist.xml.
Questo script:
  1. copia il logo in ports/images/romsorganizer.png
  2. aggiunge (o aggiorna) SOLO la voce di RomsOrganizer nel gamelist,
     preservando gli altri port gia' presenti (es. RGSX).

Eseguito da install.sh dopo l'installazione. Nessuna dipendenza esterna.
"""
from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

PORTS = Path(os.environ.get("ROMSORG_PORTS_DIR", "/userdata/roms/ports"))
LAUNCHER_PATH = "./RomsOrganizer.sh"
IMG_REL = "./images/romsorganizer.png"
SRC_IMG = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
DESC = ("Pulizia e riordino delle ROM duplicate per Batocera: file doppi, "
        "formati diversi, regioni (1G1R), gamelist. Con backup e ripristino.")


def _set(elem: ET.Element, tag: str, text: str) -> None:
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    child.text = text


def main() -> int:
    PORTS.mkdir(parents=True, exist_ok=True)

    # 1) copia immagine
    if SRC_IMG.is_file():
        (PORTS / "images").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC_IMG, PORTS / "images" / "romsorganizer.png")

    # 2) carica o crea il gamelist
    gl = PORTS / "gamelist.xml"
    if gl.is_file():
        try:
            tree = ET.parse(gl)
            root = tree.getroot()
        except ET.ParseError:
            root = ET.Element("gameList")
            tree = ET.ElementTree(root)
    else:
        root = ET.Element("gameList")
        tree = ET.ElementTree(root)

    # trova la voce esistente (per path) o creane una nuova
    game = None
    for g in root.findall("game"):
        p = g.findtext("path") or ""
        if p.strip() in (LAUNCHER_PATH, "RomsOrganizer.sh", "./RomsOrganizer.sh"):
            game = g
            break
    if game is None:
        game = ET.SubElement(root, "game")

    _set(game, "path", LAUNCHER_PATH)
    _set(game, "name", "RomsOrganizer")
    _set(game, "desc", DESC)
    if SRC_IMG.is_file():
        _set(game, "image", IMG_REL)
        _set(game, "thumbnail", IMG_REL)
        _set(game, "marquee", IMG_REL)

    tree.write(gl, encoding="utf-8", xml_declaration=True)
    print("[register_port] gamelist aggiornato:", gl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

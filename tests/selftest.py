"""Self-test del motore, eseguibile SENZA pygame e SENZA hardware Batocera.

Crea una finta cartella /roms con duplicati di ogni tipo in una dir temporanea,
fa girare i 4 motori + backup/restore + riordino, e verifica i risultati.
Serve a garantire che la logica sia sana prima ancora di toccare il mini PC.

Uso:  python3 tests/selftest.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Permette di importare il package senza installarlo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok = 0
fail = 0


def check(cond: bool, label: str) -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  \033[92mOK\033[0m  {label}")
    else:
        fail += 1
        print(f"  \033[91mNO\033[0m  {label}")


def touch(p: Path, size: int = 16) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * size)


def build_fake_roms(base: Path) -> None:
    """Costruisce uno scenario realistico di disordine."""
    # --- snes: stesso nome doppio + regioni diverse ---
    touch(base / "snes" / "Super Mario World.sfc")
    touch(base / "snes" / "Super Mario World (1).sfc")          # same_name
    touch(base / "snes" / "Super Mario Land (Japan).sfc")
    touch(base / "snes" / "Super Mario Land (Germany).sfc")     # region (1G1R)
    # regioni con priorita' nota: deve vincere Europe (Europe > USA > Japan)
    touch(base / "snes" / "Sonic (USA).sfc")
    touch(base / "snes" / "Sonic (Europe).sfc")
    touch(base / "snes" / "Sonic (Japan).sfc")

    # --- psx: formati diversi (chd vs cue+bin) ---
    touch(base / "psx" / "Crash Bandicoot.chd")
    touch(base / "psx" / "Crash Bandicoot.cue")                 # format variant
    touch(base / "psx" / "Crash Bandicoot.bin", size=2048)

    # --- psx: gioco MULTI-DISCO (non e' 1G1R!) + una seconda regione del Disco 1 ---
    touch(base / "psx" / "Final Fantasy VII (USA) (Disc 1).chd")
    touch(base / "psx" / "Final Fantasy VII (USA) (Disc 2).chd")
    touch(base / "psx" / "Final Fantasy VII (USA) (Disc 3).chd")
    touch(base / "psx" / "Final Fantasy VII (Japan) (Disc 1).chd")  # regione del SOLO disco 1

    # --- psx: tracce .bin pairate, contenuto identico ma giochi DIVERSI ---
    # Tracce audio zero-filled: stessa size e stesso hash pur essendo giochi diversi.
    # Non devono mai essere viste come "duplicato esatto" e separate dal loro .cue.
    touch(base / "psx" / "Gioco A.cue", size=200)
    touch(base / "psx" / "Gioco A (Track 3).bin", size=4096)        # zero-filled
    touch(base / "psx" / "Gioco B.cue", size=210)
    touch(base / "psx" / "Gioco B (Track 3).bin", size=4096)        # zero-filled, hash uguale

    # --- nes: una ROM finita nel sistema sbagliato (sta in 'snes') ---
    touch(base / "snes" / "Contra.nes")                         # misplaced -> nes
    touch(base / "nes" / "Contra (USA).nes")

    # --- gb: duplicati ESATTI (contenuto identico, nomi diversi) ---
    (base / "gb").mkdir(parents=True, exist_ok=True)
    (base / "gb" / "Tetris.gb").write_bytes(b"ABCD" * 100)
    (base / "gb" / "tetris_backup.gb").write_bytes(b"ABCD" * 100)   # identico -> exact
    (base / "gb" / "Alleyway.gb").write_bytes(b"WXYZ" * 100)         # stessa size, diverso

    # --- gamelist con voce orfana e voce doppia ---
    gl = base / "nes" / "gamelist.xml"
    gl.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game><path>./Contra (USA).nes</path><name>Contra (USA)</name></game>
  <game><path>./Contra (USA).nes</path><name>Contra (USA)</name></game>
  <game><path>./NonEsiste.nes</path><name>Fantasma</name></game>
</gameList>
""", encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="romsorg_test_"))
    roms = tmp / "roms"
    os.environ["ROMSORG_ROMS_DIR"] = str(roms)

    # import DOPO aver settato la env, cosi' config.roms_dir() la legge
    from RomsOrganizer.core import scanner, dedup, backup, tidy, config

    build_fake_roms(roms)
    print(f"\nScenario in: {roms}\n")

    systems = scanner.scan_systems()
    gamelists = scanner.find_gamelists()

    # 1) stesso nome
    print("[1] Stesso nome")
    same = dedup.find_same_name(systems)
    check(any(g.base.startswith("Super Mario World") for g in same),
          "trova 'Super Mario World' + '(1)'")

    # 2) formati diversi
    print("[2] Formati diversi")
    fmt = dedup.find_format_variants(systems)
    crash = [g for g in fmt if "crash" in g.base]
    check(len(crash) == 1, "trova 1 gruppo per Crash Bandicoot")
    if crash:
        keep = crash[0].candidates[crash[0].keep_index]
        check(keep.ext == "chd", "suggerisce di tenere il .chd (compresso)")

    # 3) gamelist
    print("[3] Gamelist")
    issues = dedup.find_gamelist_issues(gamelists)
    check(any(i.kind == "duplicate_entry" for i in issues), "trova la voce doppia")
    check(any(i.kind == "orphan_entry" for i in issues), "trova la voce orfana")

    # 4) regioni 1G1R
    print("[4] Regioni (1G1R)")
    reg = dedup.find_region_variants(systems)
    mario = [g for g in reg if g.base == "super mario land"]
    check(len(mario) == 1 and len(mario[0].candidates) == 2,
          "trova Mario Land Japan + Germany come UN gruppo a scelta manuale")
    # le regioni NON devono inglobare i 'same_name' (Mario World e' separato)
    check(all(g.base != "super mario world" for g in reg),
          "NON confonde le copie '(1)' con le regioni")
    # priorita' automatica: per Sonic deve suggerire di tenere Europe
    sonic = [g for g in reg if g.base == "sonic"]
    if sonic:
        kept = sonic[0].candidates[sonic[0].keep_index]
        check("(Europe)" in kept.name, "automatico: per Sonic tiene (Europe)")
    else:
        check(False, "trova il gruppo regioni di Sonic")

    # 4a) MULTI-DISCO: non deve mai essere trattato come regioni da scartare
    print("[4a] Multi-disco (FF7)")
    ff7 = [g for g in reg if g.base == "final fantasy vii"]
    # Il Disco 1 esiste in 2 regioni -> 1 solo gruppo, e SOLO fra dischi 1.
    check(len(ff7) == 1, "FF7: un solo gruppo regioni (il Disco 1 in USA+Japan)")
    if ff7:
        cands = ff7[0].candidates
        check(len(cands) == 2 and all("(Disc 1)" in c.name for c in cands),
              "FF7: il gruppo regioni contiene solo i due Disco 1")
    # NESSUN disco 2 o 3 deve mai finire fra i file da rimuovere.
    removable = {c.name for g in reg for c in g.to_remove()}
    check(not any("(Disc 2)" in n or "(Disc 3)" in n for n in removable),
          "FF7: i Dischi 2 e 3 non sono mai proposti per la rimozione")

    # 4b) duplicati esatti (hash, pre-filtro per size)
    print("[4b] Duplicati esatti (hash)")
    cands = dedup.find_exact_candidates(systems)
    names_c = {c.name for c in cands}
    check({"Tetris.gb", "tetris_backup.gb", "Alleyway.gb"} <= names_c,
          "candidati = file che condividono la dimensione")
    hashes = {str(c.path): dedup.hash_file(c.path) for c in cands}
    exact_groups = dedup.group_exact(cands, hashes)
    pair = [g for g in exact_groups
            if {c.name for c in g.candidates} == {"Tetris.gb", "tetris_backup.gb"}]
    check(len(pair) == 1, "trova la coppia identica per contenuto (nomi diversi)")
    check(all("Alleyway.gb" not in {c.name for c in g.candidates} for g in exact_groups),
          "NON raggruppa file con stessa size ma contenuto diverso")
    # Le tracce .bin pairate non vanno MAI confrontate per hash fra giochi diversi:
    # separerebbero un .cue dal suo .bin lasciando il gioco rotto.
    exact_names = {c.name for g in exact_groups for c in g.candidates}
    check("Gioco A (Track 3).bin" not in exact_names
          and "Gioco B (Track 3).bin" not in exact_names,
          "NON raggruppa per hash le tracce .bin pairate di giochi diversi")
    cand_names = {c.name for c in cands}
    check("Gioco A (Track 3).bin" not in cand_names,
          "le tracce .bin pairate sono escluse dai candidati hash")

    # 5) backup + restore
    print("[5] Backup e ripristino")
    target = same[0].to_remove()[0]
    orig = target.path
    backup.move_to_backup(target, reason="same_name")
    check(not orig.exists(), "la ROM e' stata spostata via dall'originale")
    check(config.backup_dir().exists(), "esiste la cartella 'ROM eliminate'")
    summ = backup.backup_summary()
    check(summ["count"] == 1, "il manifest registra 1 voce")
    backup.restore_all()
    check(orig.exists(), "il ripristino la rimette al suo posto")
    check(backup.backup_summary()["count"] == 0, "manifest svuotato dopo restore")

    # 6) riordino: ROM nel sistema giusto
    print("[6] Riordino - sistema giusto")
    mis = tidy.find_misplaced(systems)
    contra = [m for m in mis if m["rom"].name == "Contra.nes"]
    check(len(contra) == 1 and contra[0]["to"] == "nes",
          "Contra.nes va spostata da snes a nes")

    # 7) riordino: gamelist
    print("[7] Riordino - gamelist")
    res = tidy.tidy_gamelist(gamelists["nes"])
    check(res["removed_dup"] >= 1, "rimuove la voce doppia")
    check(res["removed_orphan"] >= 1, "rimuove la voce orfana")

    # 8) pulizia nomi
    print("[8] Riordino - nomi puliti")
    changes = tidy.clean_display_names(scanner.find_gamelists(), dry_run=True)
    check(any(c["new"] == "Contra" for c in changes),
          "'Contra (USA)' -> 'Contra' nel nome mostrato")

    print(f"\nRisultato: {ok} OK, {fail} NO\n")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

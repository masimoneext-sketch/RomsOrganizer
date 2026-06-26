<div align="center">
  <img src="RomsOrganizer/assets/logo.png" alt="RomsOrganizer" width="320">
  <h1>RomsOrganizer</h1>
  <p><b>Pulizia e riordino delle ROM per Batocera</b> · <i>ROM cleanup & tidy for Batocera</i></p>
</div>

---

## 🇮🇹 Italiano

RomsOrganizer è un'app per **Batocera** che trova e rimuove le ROM duplicate dalle
tue liste, con **backup e ripristino** integrati. Si installa da GitHub e compare
nel menu **PORTS**, navigabile col controller (interfaccia pygame in stile arcade).

### Cosa fa
- **File doppi (stesso nome)** — `Game.zip` + `Game (1).zip`, copie sparse.
- **Formati diversi** — stesso gioco in `.cue/.bin` e `.chd`: tieni quello che vuoi.
- **Regioni/revisioni (1G1R)** — `Mario (Japan)` vs `Mario (Europe)`: scegli **a mano**.
- **Duplicati esatti (hash)** — stesso contenuto byte-per-byte anche con nomi diversi.
- **Gamelist** — rimuove voci doppie e orfane, riordina alfabeticamente.
- **Riordino** — pulisce i nomi mostrati e sposta le ROM nel sistema giusto.

> **Giochi multi-disco al sicuro**: `(Disc 1/2/3)` non vengono mai scambiati per
> regioni alternative. Il 1G1R confronta solo dischi con lo **stesso indice**
> (`FF7 (USA) Disc 1` vs `FF7 (Japan) Disc 1`), mai Disco 1 contro Disco 2.

### Sicurezza
- **Non cancella mai**: i duplicati vengono spostati nella cartella `ROM eliminate`.
- **Ripristino** completo da menu (registro `manifest`).
- **Anteprima (dry-run)** prima di ogni operazione: vedi cosa farà, poi confermi.
- **Set `.cue`/`.bin` mai separati**: le tracce pairate (`cue/bin/ccd/sub`) non
  vengono confrontate per hash, così un `.cue` non resta mai senza il suo `.bin`.

### Installazione
Da terminale Batocera (SSH o console):
```sh
curl -L https://raw.githubusercontent.com/masimoneext-sketch/RomsOrganizer/main/install.sh | sh
```
Poi: **Menu → Impostazioni giochi → Aggiorna lista giochi**.
Trovi *RomsOrganizer* nella sezione **PORTS**.

### Comandi
| Azione | Controller | Tastiera |
|---|---|---|
| Muovi | D-pad / stick | frecce / WASD |
| Conferma | A (configurabile) | Invio |
| Indietro | B (configurabile) | Esc |
| Scegli "tieni" | X | Spazio |

Al **primo avvio** col controller parte la configurazione tasti (come RGSX).

---

## 🇬🇧 English

RomsOrganizer is a **Batocera** app that finds and removes duplicate ROMs from your
game lists, with built-in **backup and restore**. Installs from GitHub and shows up
in the **PORTS** menu, controller-friendly (arcade-style pygame UI).

### Features
- **Duplicate files** (same name), **format variants** (`.cue/.bin` vs `.chd`),
  **region/revision** duplicates (1G1R, **manual** pick), **exact content** dupes
  (byte-for-byte hash), **gamelist** cleanup (duplicate/orphan entries + sorting),
  **tidy** (clean names, move ROMs to the right system).
- **Multi-disc safe**: `(Disc 1/2/3)` are never mistaken for alternate regions —
  1G1R only compares discs with the **same index** across regions.

### Safety
- **Never deletes**: duplicates are moved to the `ROM eliminate` folder, with full
  **restore** from the menu and a **dry-run preview** before every action.
- **`.cue`/`.bin` sets are never split**: paired tracks (`cue/bin/ccd/sub`) are
  excluded from hash matching, so a `.cue` is never left without its `.bin`.

### Install
```sh
curl -L https://raw.githubusercontent.com/masimoneext-sketch/RomsOrganizer/main/install.sh | sh
```
Then **Menu → Game settings → Update game list**, find *RomsOrganizer* under **PORTS**.

---

## 🛠️ Sviluppo / Development

Il **motore** (`RomsOrganizer/core/`) è Python puro, senza pygame: testabile ovunque.

```sh
python3 tests/selftest.py     # crea ROM finte e verifica i 5 motori + backup/restore
```

La **UI** (`RomsOrganizer/ui/`) usa pygame ed è un guscio sopra il motore.

```
RomsOrganizer/
├── core/        motore: scanner, dedup, backup, tidy, config, models
├── ui/          pygame: app (schermate), controls, theme, strings
├── i18n/        traduzioni it/en
└── assets/      logo
```

> Requisiti: Python 3 (incluso in Batocera) e pygame (di norma già presente).

## 🎵 Musica / Credits

Musica di sottofondo (attivabile/disattivabile dal menu **Musica: ON/OFF**):

> **"Climbers In The Dark"** by **Nihilore** — licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
> Source: [Free Music Archive](https://freemusicarchive.org/music/Nihilore/it-is-still-happening-it-should-not-be-happening/climbers-in-the-dark/).

Vedi [assets/CREDITS.md](RomsOrganizer/assets/CREDITS.md).

## Licenza
Codice: MIT — non affiliato a Batocera, RetroBat o RGS.
Musica: CC BY 4.0 (vedi sopra).

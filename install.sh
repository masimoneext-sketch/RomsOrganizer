#!/bin/sh
# Installer di RomsOrganizer per Batocera (modello RGSX).
# Uso:  curl -L https://raw.githubusercontent.com/masimoneext-sketch/RomsOrganizer/main/install.sh | sh
#
# Scarica l'app in /userdata/roms/ports/RomsOrganizer e crea il launcher che
# la fa comparire nel menu PORTS. Non tocca nient'altro del sistema.
set -e

REPO="masimoneext-sketch/RomsOrganizer"
BRANCH="main"
PORTS="/userdata/roms/ports"
APPDIR="$PORTS/RomsOrganizer"
LAUNCHER="$PORTS/RomsOrganizer.sh"
TARBALL="https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz"
TMP="$(mktemp -d)"

echo ""
echo "================================================"
echo "  RomsOrganizer - installazione su Batocera"
echo "================================================"

mkdir -p "$PORTS"

echo "[1/4] Scarico l'app da GitHub..."
curl -L "$TARBALL" -o "$TMP/app.tar.gz"

echo "[2/4] Estraggo..."
tar -xzf "$TMP/app.tar.gz" -C "$TMP"
SRC="$TMP/RomsOrganizer-$BRANCH"

echo "[3/4] Installo in $APPDIR ..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR"
# copia il package python (la cartella interna RomsOrganizer/)
cp -r "$SRC/RomsOrganizer/." "$APPDIR/"

echo "[4/5] Creo il launcher nel menu PORTS..."
cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
# Launcher RomsOrganizer - avvia l'app pygame dal menu PORTS di Batocera.
cd /userdata/roms/ports
python3 -m RomsOrganizer
EOF
chmod +x "$LAUNCHER"

echo "[5/5] Registro il logo nel menu PORTS..."
python3 "$APPDIR/tools/register_port.py" || echo "  (avviso: anteprima non registrata, l'app funziona comunque)"

rm -rf "$TMP"

# Come RGSX: chiede a EmulationStation di rileggere i gamelist dal disco, cosi'
# l'immagine appena scritta compare subito e ES non la sovrascrive piu'.
echo "  Aggiorno la lista giochi di EmulationStation..."
curl -s "http://127.0.0.1:1234/reloadgames" >/dev/null 2>&1 \
  && echo "  Lista giochi ricaricata." \
  || echo "  (se non vedi l'anteprima, riavvia EmulationStation)"

echo ""
echo "  Fatto!"
echo "  Trovi 'RomsOrganizer' nella sezione PORTS (con l'immagine)."
echo "================================================"
echo ""

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

echo "[4/4] Creo il launcher nel menu PORTS..."
cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
# Launcher RomsOrganizer - avvia l'app pygame dal menu PORTS di Batocera.
cd /userdata/roms/ports
python3 -m RomsOrganizer
EOF
chmod +x "$LAUNCHER"

rm -rf "$TMP"

echo ""
echo "  Fatto!"
echo "  Ora su Batocera:  Menu > Impostazioni giochi > Aggiorna lista giochi"
echo "  Poi trovi 'RomsOrganizer' nella sezione PORTS."
echo "================================================"
echo ""

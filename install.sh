#!/bin/zsh
# Install (or reinstall) AutoSlotSelector into the Live app bundle.
# Re-run after every Live update — updates replace the bundle and drop the folder.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-/Applications/Ableton Live 12 Suite.app}"
DEST="$APP/Contents/App-Resources/MIDI Remote Scripts/AutoSlotSelector"
[ -d "$APP" ] || { echo "no Live app at: $APP" >&2; exit 1; }
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$HERE/AutoSlotSelector/__init__.py" "$HERE/AutoSlotSelector/AutoSlotSelector.py" "$DEST/"
echo "installed -> $DEST"
echo "restart Live, then watch:  tail -f ~/Library/Preferences/Ableton/Live\ 12*/Log.txt | grep -i autoslot"

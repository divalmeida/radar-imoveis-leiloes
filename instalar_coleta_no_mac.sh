#!/bin/bash
# Instala (ou reinstala) a coleta da Caixa no Mac: 08:05 e 19:05 todos os dias.
# Se o Mac estiver dormindo nesse horário, roda quando ele acordar.
set -e
BASE="$HOME/Library/Application Support/RadarLocal"
REPO="$BASE/repo"
PLIST="$HOME/Library/LaunchAgents/com.radar.coleta-mac.plist"
PY="$(command -v python3)"
mkdir -p "$BASE"
if [ ! -d "$REPO/.git" ]; then
  git clone -q https://github.com/divalmeida/radar-imoveis-leiloes.git "$REPO"
  git -C "$REPO" remote set-url --push origin git@github.com:divalmeida/radar-imoveis-leiloes.git
fi
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.radar.coleta-mac</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$REPO/coletar_no_mac.py</string></array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>5</integer></dict>
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$BASE/coleta.log</string>
  <key>StandardErrorPath</key><string>$BASE/coleta.log</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/com.radar.coleta-mac" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Instalado. Registro em: $BASE/coleta.log"

#!/usr/bin/env bash
# Remove o que o install.sh instalou. As preferências do usuário (~/.config/lumen) ficam.
# Uso: sudo ./uninstall.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Rode com sudo: sudo ./uninstall.sh" >&2
    exit 1
fi

rm -rf /opt/lumen
rm -f /usr/local/bin/lumen /usr/share/applications/lumen.desktop \
      /usr/share/icons/hicolor/256x256/apps/lumen.png /etc/udev/rules.d/70-lumen.rules
udevadm control --reload-rules || true
echo "Lumen removido. Suas preferências continuam em ~/.config/lumen."

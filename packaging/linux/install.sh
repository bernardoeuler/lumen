#!/usr/bin/env bash
# Instala o Lumen em /opt/lumen, com atalho no menu, ícone e a regra do udev que dá acesso ao controle.
# Uso: sudo ./install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Rode com sudo: sudo ./install.sh" >&2
    exit 1
fi
aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

rm -rf /opt/lumen
cp -r "$aqui/lumen" /opt/lumen
chmod 755 /opt/lumen/lumen
ln -sf /opt/lumen/lumen /usr/local/bin/lumen

install -Dm644 "$aqui/lumen.desktop" /usr/share/applications/lumen.desktop
install -Dm644 "$aqui/lumen.png" /usr/share/icons/hicolor/256x256/apps/lumen.png
install -Dm644 "$aqui/70-lumen.rules" /etc/udev/rules.d/70-lumen.rules

udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true

echo "Lumen instalado. Abra pelo menu de aplicativos ou rode: lumen"
echo "Se o controle já estava conectado, desconecte e conecte de novo para a permissão valer."

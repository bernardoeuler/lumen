#!/usr/bin/env bash
# Gera o build de produção com Nuitka no Linux: build/lumen/lumen (modo pasta, um processo).
# Requer: python -m pip install -r requirements-dev.txt (wxPython de extras.wxpython.org, ver README)
#         e patchelf (sudo apt install patchelf).
#
# Uso:
#   ./build.sh                    # usa o Python do .venv (ou python3)
#   ./build.sh --pacote           # também gera dist/lumen-<versão>-linux-x86_64.tar.gz
#   PYTHON=python ./build.sh ...  # outro Python (CI)
set -euo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
saida="$raiz/build"
if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x "$raiz/.venv/bin/python" ]]; then PYTHON="$raiz/.venv/bin/python"; else PYTHON=python3; fi
fi
pacote=false
[[ "${1:-}" == "--pacote" ]] && pacote=true

versao="$("$PYTHON" -c "import sys; sys.path.insert(0, '$raiz'); import versao; print(versao.VERSAO)")"
echo "Lumen $versao"
mkdir -p "$saida"

"$PYTHON" -m nuitka \
    --standalone \
    --lto=yes \
    --assume-yes-for-downloads \
    --output-dir="$saida" \
    --output-filename=lumen \
    "$raiz/app.py"

# o Nuitka gera build/app.dist; entrega como build/lumen
rm -rf "$saida/lumen"
mv "$saida"/*.dist "$saida/lumen"
echo "Build pronto: $saida/lumen/lumen"

if $pacote; then
    nome="lumen-$versao-linux-x86_64"
    temp="$(mktemp -d)"
    trap 'rm -rf "$temp"' EXIT
    mkdir -p "$temp/$nome"
    cp -r "$saida/lumen" "$temp/$nome/lumen"
    cp "$raiz"/packaging/linux/{70-lumen.rules,lumen.desktop,install.sh,uninstall.sh} "$temp/$nome/"
    cp "$raiz/assets/lumen.png" "$raiz/README.md" "$temp/$nome/"
    [[ -f "$raiz/LICENSE" ]] && cp "$raiz/LICENSE" "$temp/$nome/"
    chmod +x "$temp/$nome/install.sh" "$temp/$nome/uninstall.sh" "$temp/$nome/lumen/lumen"
    mkdir -p "$raiz/dist"
    tar -C "$temp" -czf "$raiz/dist/$nome.tar.gz" "$nome"
    echo "Pacote: $raiz/dist/$nome.tar.gz"
fi

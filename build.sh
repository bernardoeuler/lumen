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

# O Nuitka não copia bibliotecas do sistema, mas o wxPython do Linux depende de algumas que não vêm em
# toda instalação ou mudam de versão entre distribuições (ex.: libtiff.so.5 só existe até o Ubuntu
# 22.04). Essas vão junto no pacote; as do núcleo (glibc, GTK, GLib, X11/Wayland, GL) continuam vindo
# do sistema. Os binários já procuram bibliotecas em $ORIGIN (RPATH do Nuitka).
# (libjpeg.so.8: o Debian usa a .so.62, com outro nome, então não há conflito)
incluir='lib(tiff|jpeg|SDL2-2\.0|notify|secret-1|pcre2-32|jbig|deflate|Lerc|Xxf86vm)\.so'
# carregadas em tempo de execução (dlopen), então o ldd não as mostra: vão pelo nome
extras=(libXxf86vm.so.1)
for _ in 1 2 3; do  # repete para pegar as dependências das próprias bibliotecas incluídas
    {
        find "$saida/lumen" -type f \( -name '*.so*' -o -name lumen \) -exec ldd {} \; 2>/dev/null \
            | awk '/=> \// { print $3 }' | grep -E "/$incluir"
        for nome in "${extras[@]}"; do ldconfig -p | awk -v n="$nome" '$1 == n && /x86-64/ { print $NF; exit }'; done
    } | sort -u | while read -r lib; do
            nome="$(basename "$lib")"
            [[ -e "$saida/lumen/$nome" ]] && continue
            cp -L "$lib" "$saida/lumen/$nome"
            patchelf --set-rpath '$ORIGIN' "$saida/lumen/$nome"
            echo "incluída: $nome"
        done
done
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

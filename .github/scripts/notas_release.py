"""Monta as notas da release: a seção da versão no CHANGELOG.md + instruções de instalação.

Uso: python .github/scripts/notas_release.py 1.2.3 > notas.md
Falha se o CHANGELOG.md não tiver a seção "## [1.2.3]" (obriga a registrar a mudança).
"""
import re
import sys
from pathlib import Path

INSTALACAO = """
## Instalação

**Windows (10/11, x64):** baixe `lumen-{v}-windows-x64.zip`, extraia e abra `lumen\\lumen.exe`.
Não precisa instalar nada; a pasta inteira é o programa.

**Linux (x86_64, glibc 2.35+ — Ubuntu 22.04, Debian 12, Fedora 36 ou mais novos):** precisa das bibliotecas
que todo desktop já tem (GTK 3, áudio, Mesa). Testado em Ubuntu 22.04, Ubuntu 24.04 e Debian 12.

```bash
tar -xzf lumen-{v}-linux-x86_64.tar.gz
cd lumen-{v}-linux-x86_64
sudo ./install.sh
```

O `install.sh` coloca o app em `/opt/lumen`, cria o atalho no menu e instala a regra do udev que dá
acesso ao controle sem root. Para remover: `sudo ./uninstall.sh`.

Confira a integridade dos arquivos com `SHA256SUMS.txt` (`sha256sum -c SHA256SUMS.txt`).
"""


def secao(changelog, versao):
    padrao = rf"^## \[{re.escape(versao)}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    achou = re.search(padrao, changelog, re.MULTILINE | re.DOTALL)
    return achou.group(1).strip() if achou else None


def main():
    versao = sys.argv[1]
    changelog = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text(encoding="utf-8")
    texto = secao(changelog, versao)
    if not texto:
        sys.exit(f"CHANGELOG.md não tem a seção [{versao}]")
    sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    print(INSTALACAO.format(v=versao))


if __name__ == "__main__":
    main()

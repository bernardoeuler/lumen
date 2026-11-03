# Lumen

Controle a **luz**, o **pisca** e a **vibração** do seu controle de PS4 (DualShock 4), e veja a
**bateria** dele, por Bluetooth ou USB, no Windows e no Linux. Feito pensando também nos controles
**paralelos (clones)**, que ignoram parte dos comandos do original.

[![CI](https://github.com/bernardoeuler/lumen/actions/workflows/ci.yml/badge.svg)](https://github.com/bernardoeuler/lumen/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/bernardoeuler/lumen)](https://github.com/bernardoeuler/lumen/releases/latest)

## Recursos

- Cores prontas, seletor de cor, brilho e "Apagar".
- Pisca com uma sequência de cores e pausas, cada uma com sua duração (arraste para reordenar).
- Vibração dos dois motores e padrões de vibração, uma vez ou repetindo.
- "Sincronizar com a luz": pisca e vibração começam juntos.
- Nível de bateria e carregamento.
- Presets `.lumen.json` para importar e exportar suas configurações.
- Fica na bandeja do sistema; reconecta sozinho quando o controle volta.

## Download

Baixe a versão mais recente em **[Releases](https://github.com/bernardoeuler/lumen/releases/latest)**.

### Windows (10/11, x64)

Extraia `lumen-<versão>-windows-x64.zip` e abra `lumen\lumen.exe`. Não precisa instalar.

### Linux (x86_64)

Requer glibc 2.35 ou mais nova (Ubuntu 22.04, Debian 12, Fedora 36 ou mais novos) e GTK 3.

```bash
tar -xzf lumen-<versão>-linux-x86_64.tar.gz
cd lumen-<versão>-linux-x86_64
sudo ./install.sh
```

O instalador coloca o app em `/opt/lumen`, cria o atalho no menu e instala uma regra do udev para o
seu usuário acessar o controle sem root. Para remover: `sudo ./uninstall.sh`.

## Dicas

- **Steam aberta assume o controle** (Steam Input) e sobrescreve a luz. Feche a Steam, ou desative o
  Steam Input para controles de PlayStation, enquanto usa o Lumen.
- Fechar a janela deixa o Lumen na bandeja; para encerrar, use **Sair** no ícone da bandeja.
- Preferências e log: `%LOCALAPPDATA%\Lumen` (Windows) ou `~/.config/lumen` (Linux).

## Presets (`.lumen.json`)

Um preset guarda luz, pisca e vibração num arquivo só. Todas as seções são opcionais: um arquivo só
com `light` muda só a luz.

```json
{
  "format": "lumen-preset",
  "version": 1,
  "name": "Alerta",
  "light": {
    "color": "#00FFFF",
    "brightness": 100,
    "blink": {
      "enabled": true,
      "steps": [
        { "color": "#FF0000", "duration": 0.5 },
        { "off": true, "duration": 0.3 }
      ]
    }
  },
  "vibration": {
    "pulse": { "strong": 255, "weak": 255, "duration": 1.0 },
    "pattern": {
      "repeat": true,
      "steps": [
        { "strong": 255, "weak": 0, "duration": 0.3 },
        { "off": true, "duration": 0.2 }
      ]
    }
  },
  "sync": true
}
```

Durações em segundos (0,05 a 10), intensidades de 0 a 255 e brilho em %. Valores fora da faixa são
limitados e passos inválidos são descartados, com aviso. A especificação completa está em
[`preset.py`](preset.py).

## Desenvolvimento

Requer Python 3.11.

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\pythonw.exe app.py      # rodar
.\.venv\Scripts\python.exe -m pytest    # testes
.\build.ps1                             # build em build\lumen\lumen.exe
```

```bash
# Linux (o wxPython vem de extras.wxpython.org, pois o PyPI não tem wheel para Linux)
sudo apt install patchelf libgtk-3-0 libnotify4 libsdl2-2.0-0
python3 -m venv .venv
.venv/bin/pip install --only-binary wxPython \
  -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04/ -r requirements-dev.txt
.venv/bin/python app.py                 # rodar
.venv/bin/python -m pytest              # testes
./build.sh                              # build em build/lumen/lumen
```

### Publicar uma versão

1. Atualize `VERSAO` em [`versao.py`](versao.py) e registre as mudanças no [`CHANGELOG.md`](CHANGELOG.md).
2. Faça o commit, crie a tag e envie:
   ```bash
   git tag v1.2.3
   git push origin main v1.2.3
   ```
3. O workflow [Release](.github/workflows/release.yml) gera os pacotes de Windows e Linux, as somas
   SHA-256 e publica a release com as notas do CHANGELOG. Tags com sufixo (ex.: `v1.2.3-rc.1`) saem
   como pré-release.

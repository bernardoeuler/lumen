# Lumen

Ferramenta para controlar um controle de PS4 **paralelo (clone)** por Bluetooth ou USB, no **Windows e
no Linux**: luz, pisca, vibração e bateria. Um único programa com GUI, no modelo do DS4Windows.

Antes se chamou Faísca e, no começo, ds4-cli (a pasta local do projeto ainda tem esse nome). O `config.py` renomeia sozinho a
pasta de dados antiga. Repositório: https://github.com/bernardoeuler/lumen

## Arquivos

- `app.py`: GUI (wxPython) e bandeja; ponto de entrada. `--version` imprime a versão e sai (sem janela).
- `versao.py`: **versão única** do app (`VERSAO`, semver) e URL do repositório.
- `gerenciador.py`: dono do controle; guarda o estado (cor, pisca, vibração) e o envia numa thread,
  reconectando sozinho.
- `instancia.py`: instância única; escolhe `instancia_windows.py` (named pipe via ctypes) ou
  `instancia_unix.py` (socket Unix abstrato, Linux).
- `config.py`: preferências do usuário em `%LOCALAPPDATA%\Lumen\config.json` (Windows) ou
  `~/.config/lumen/config.json` (Linux), restauradas ao abrir o app.
- `preset.py`: import/export de presets `.lumen.json` (formato próprio, versão 1, documentado no topo do
  arquivo): luz, pisca e vibração num documento, seções opcionais, chaves em inglês. Importação tolerante
  (limita valores, descarta passos ruins, avisa); recusa o que não for preset do Lumen.
- `controle.py`: acesso HID de baixo nível (achar, abrir, montar e enviar o relatório de saída). No Linux o
  wheel do `hidapi` traz dois módulos: `hid` (libusb, **não enxerga Bluetooth**) e `hidraw`; o
  `controle.py` importa `hidraw` no Linux (teste em `tests/test_controle.py`). Acesso sem root pela
  regra do udev.
- `testar_luz.py`, `testar_apagar.py`, `testar_bateria.py`: diagnósticos direto no HID.
- `tests/`: pytest da lógica sem GUI (preset, gerenciador). `python -m pytest`.
- `assets/`: ícones (`lumen.ico` do exe, `lumen.png` do Linux), gerados com `criar_imagem` do `app.py`.
- `build.ps1` (Windows) e `build.sh` (Linux): build com Nuitka; `-Pacote`/`--pacote` gera o zip/tar.gz em `dist/`.
- `packaging/linux/`: regra do udev, `.desktop`, `install.sh` e `uninstall.sh` que vão no tar.gz.
- `.github/workflows/`: `ci.yml` (testes em Windows e Linux) e `release.yml` (ver "Releases").
- `CHANGELOG.md`: Keep a Changelog; a seção da versão vira as notas da release.
- Rodar em desenvolvimento: `.\.venv\Scripts\pythonw.exe app.py`
- Log: `lumen.log` na pasta de dados.

## Particularidades do controle (clone)

Ele se identifica como DualShock 4 v2 da Sony: VID `054C`, PID `09CC`.

- **Luz:** só funciona se o relatório Bluetooth (0x11) tiver o byte 2 = `0x00` e as **três flags** juntas
  (`0x07`: vibração, luz e pisca). Só a flag da luz é ignorada. Confirmado com `testar_luz.py`, com e sem Steam.
- **Pisca por hardware** (bytes de aceso/apagado do relatório) é ignorado; o pisca é feito por software.
- **Cor (0, 0, 0) deixa a luz BRANCA**, não apagada. Nenhum comando apaga de vez (`testar_apagar.py`:
  flags sem luz e pisca de hardware são ignorados). O mais perto de apagado é uma cor com canais em 1
  (brilho bem fraco). O `app.py` manda o **tom apagado da cor em uso** (`tom_apagado`: cada canal aceso
  vira 1): no Apagar, o da cor da luz; nas pausas do pisca, o da cor acesa anterior. Se ainda chegar
  (0, 0, 0) ao `controle.py`, ele usa `COR_APAGADA` = (0, 0, 1). Na tela, "apagado" continua (0, 0, 0).
- Por isso todo relatório leva o estado completo (cor + motores).
- **Bateria:** como no DS4 original, byte 32 do relatório de entrada Bluetooth (0x11; 30 no USB 0x01):
  nível nos 4 bits de baixo (0..10, 10 = cheia) e 0x10 = cabo. O controle só manda o 0x11 depois de
  receber relatórios de saída, o que o app faz o tempo todo. Leitura sem bloquear em `DS4.ler_bateria()`.
- **Steam aberta** sobrescreve a luz (Steam Input é dono do controle). Testar com ela fechada.

## Arquitetura (decidida, modelo DS4Windows)

- **Um único programa com GUI**, que é o próprio dono do controle. **Sem servidor separado e sem CLI.**
- **Fechar a janela minimiza para a bandeja**; o controle continua gerenciado. O programa só encerra
  pelo **Sair** no ícone da bandeja. Ao encerrar: para os motores e mantém a cor da luz. Se não houver
  bandeja (alguns ambientes Linux), fechar encerra.
- **Instância única:** a primeira instância ouve (named pipe no Windows, socket Unix abstrato no Linux);
  ao abrir o programa de novo, a nova instância avisa a que já está rodando (para mostrar a janela) e
  encerra, sem tocar no controle.
- Dentro do programa: a GUI na thread principal, o envio ao controle (estado + pisca + vibração +
  reconexão) na thread do `gerenciador.py` e a instância única numa terceira. Só a thread da GUI mexe na
  tela (use `wx.CallAfter`).
- Código específico do Windows (DPI, `AllowSetForegroundWindow`, balão da bandeja) fica protegido por
  `sys.platform == "win32"` ou `hasattr`.
- Opcional/futuro: iniciar com o sistema.
- **Biblioteca de GUI: wxPython** (decisão atual). Bandeja com `wx.adv.TaskBarIcon`, seletor de cor
  nativo `wx.ColourDialog`. Atualizações vindas da thread do controle para a GUI via `wx.CallAfter`.
- Layout: evitar `wx.WrapSizer` dentro de `StaticBox` (calcula mal a altura e esconde o que quebra
  linha). Tamanhos fixos sempre com `FromDIP`. Bolinhas de cor, prévia e indicador são desenhados à mão
  (`wx.GraphicsContext`), para terem forma redonda e anel de seleção. Opções secundárias (presets, Sobre)
  ficam no menu do botão "⋯" do cabeçalho, para não poluir a tela.
- **Escopo atual: só luz, pisca, vibração e indicador de bateria.** Não implementar remapeamento nem gráficos sem pedido.
  Se o projeto crescer para isso, reavaliar PySide6 + pyqtgraph; o remapeamento exigiria ler a entrada
  do controle, um controle de Xbox virtual (ViGEmBus, já instalado, via `vgamepad`) e esconder o
  controle real (HidHide, não instalado).

## Empacotamento (decidido)

- **Nuitka no modo pasta (`--standalone`)**, pelo binário mais rápido. **Nunca `--onefile`** (cria 2 processos).
- **Um executável, um processo**: `lumen.exe` (sem console) / `lumen` no Linux.
- No código: threads, nunca `multiprocessing`; na GUI, evitar `QtWebEngine` (cria processos auxiliares).
- Em **desenvolvimento** é aceitável ter 2 processos (o `pythonw.exe` do venv é um lançador que abre o
  Python do sistema). Não otimizar isso; só a produção precisa de 1 processo.
- Logs e configurações na pasta de dados do usuário (a pasta do programa pode não ser gravável).
- **wxPython:** 4.3.2 no Windows (PyPI); no Linux o PyPI não tem wheel, então usa a 4.2.5 de
  extras.wxpython.org (ubuntu-22.04), via marcador de plataforma no `requirements.txt`. Não usar API
  exclusiva da 4.3.
- **Como gerar (Windows):** `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` e depois
  `powershell -ExecutionPolicy Bypass -File .\build.ps1`. Saída: `build\lumen\lumen.exe` (a pasta inteira
  é o programa). Usa o MSVC do Visual Studio e `--lto=yes`; leva alguns minutos. O `build.ps1` precisa
  ficar em UTF-8 **com BOM** (o PowerShell 5.1 lê sem BOM como ANSI).
- `--output-folder-name` do Nuitka não tem efeito aqui; os scripts renomeiam o `*.dist` para `build/lumen`.
- A declaração de DPI é feita em código (`declarar_dpi()` no `app.py`), porque o Nuitka não tem opção
  de manifesto para isso.
- Primeiro build (Nuitka 4.3.4, wxPython 4.3.2): ~37 MB, 19 arquivos, ~40 MB de memória rodando.

## Releases

- Push de tag `vX.Y.Z` dispara `release.yml`: confere tag = `versao.py`, gera Windows (zip) e Linux
  (tar.gz, Ubuntu 22.04 para glibc mais antiga), testa `--version` dos executáveis, gera
  `SHA256SUMS.txt` e publica com as notas da seção do `CHANGELOG.md` (falha se ela não existir).
  Tag com sufixo (`-rc.1`) sai como pré-release. Rodar à mão (`workflow_dispatch`) só gera os artefatos.
- Para lançar: subir `VERSAO`, escrever a seção no CHANGELOG, commit, `git tag vX.Y.Z`, push da tag.
- O push usa HTTPS com o login do `gh` (não há chave SSH): `git -c credential.helper= -c
  'credential.helper=!gh auth git-credential' push`.

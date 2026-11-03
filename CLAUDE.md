# ds4-cli

Ferramenta para controlar um controle de PS4 **paralelo (clone)** conectado por Bluetooth no Windows:
luz, pisca e vibração. Um único programa com GUI, no modelo do DS4Windows.

## Arquivos

- `app.py`: GUI (wxPython) e bandeja; ponto de entrada.
- `gerenciador.py`: dono do controle; guarda o estado (cor, pisca, vibração) e o envia numa thread,
  reconectando sozinho.
- `instancia.py`: instância única via named pipe (ctypes, sem dependência extra).
- `config.py`: preferências do usuário (cor, brilho, pisca, vibração) em `%LOCALAPPDATA%\ds4-cli\config.json`,
  restauradas ao abrir o app.
- `controle.py`: acesso HID de baixo nível (achar, abrir, montar e enviar o relatório de saída).
- `testar_luz.py`: testa variantes do relatório de luz direto no HID (com o app fechado).
- `build.ps1`: build de produção com Nuitka (ver "Empacotamento").
- Rodar em desenvolvimento: `.\.venv\Scripts\pythonw.exe app.py`
- Log: `%LOCALAPPDATA%\ds4-cli\ds4.log`

## Particularidades do controle (clone)

Ele se identifica como DualShock 4 v2 da Sony: VID `054C`, PID `09CC`.

- **Luz:** só funciona se o relatório Bluetooth (0x11) tiver o byte 2 = `0x00` e as **três flags** juntas
  (`0x07`: vibração, luz e pisca). Só a flag da luz é ignorada. Confirmado com `testar_luz.py`, com e sem Steam.
- **Pisca por hardware** (bytes de aceso/apagado do relatório) é ignorado; o pisca é feito por software.
- Por isso todo relatório leva o estado completo (cor + motores).
- **Steam aberta** sobrescreve a luz (Steam Input é dono do controle). Testar com ela fechada.

## Arquitetura (decidida, modelo DS4Windows)

- **Um único programa com GUI**, que é o próprio dono do controle. **Sem servidor separado e sem CLI.**
- **Fechar a janela minimiza para a bandeja**; o controle continua gerenciado. O programa só encerra
  pelo **Sair** no ícone da bandeja. Ao encerrar: para os motores e mantém a cor da luz.
- **Instância única via named pipe:** a primeira instância cria o pipe; ao abrir o programa de novo, a
  nova instância avisa a que já está rodando (para mostrar a janela) pelo pipe e encerra, sem tocar no
  controle.
- Dentro do programa: a GUI na thread principal, o envio ao controle (estado + pisca + vibração +
  reconexão) na thread do `gerenciador.py` e o pipe numa terceira. Só a thread da GUI mexe na tela
  (use `wx.CallAfter`).
- Opcional/futuro: iniciar com o Windows (atalho na pasta Inicializar ou tarefa ao fazer logon).
- **Biblioteca de GUI: wxPython** (decisão atual). Bandeja com `wx.adv.TaskBarIcon`, seletor de cor
  nativo `wx.ColourDialog`. Atualizações vindas da thread do controle para a GUI via `wx.CallAfter`.
- Layout: evitar `wx.WrapSizer` dentro de `StaticBox` (calcula mal a altura e esconde o que quebra
  linha). Tamanhos fixos sempre com `FromDIP`. Bolinhas de cor, prévia e indicador são desenhados à mão
  (`wx.GraphicsContext`), para terem forma redonda e anel de seleção.
- **Escopo atual: só luz, pisca e vibração.** Não implementar remapeamento nem gráficos sem pedido.
  Se o projeto crescer para isso, reavaliar PySide6 + pyqtgraph; o remapeamento exigiria ler a entrada
  do controle, um controle de Xbox virtual (ViGEmBus, já instalado, via `vgamepad`) e esconder o
  controle real (HidHide, não instalado).

## Empacotamento (decidido)

- **Nuitka no modo pasta (`--standalone`)**, pelo binário mais rápido. **Nunca `--onefile`** (cria 2 processos).
- **Um executável, um processo**: `ds4.exe`, sem console.
- No código: threads, nunca `multiprocessing`; na GUI, evitar `QtWebEngine` (cria processos auxiliares).
- Em **desenvolvimento** é aceitável ter 2 processos (o `pythonw.exe` do venv é um lançador que abre o
  Python do sistema). Não otimizar isso; só a produção precisa de 1 processo.
- Logs e configurações em `%LOCALAPPDATA%\ds4-cli\` (a pasta do programa pode não ser gravável).
- **Como gerar:** `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` e depois
  `powershell -ExecutionPolicy Bypass -File .\build.ps1`. Saída: `build\ds4\ds4.exe` (a pasta inteira
  é o programa). Usa o MSVC do Visual Studio e `--lto=yes`; leva alguns minutos.
- `--output-folder-name` do Nuitka não tem efeito aqui; o `build.ps1` renomeia o `*.dist` para `build\ds4`.
- A declaração de DPI é feita em código (`declarar_dpi()` no `app.py`), porque o Nuitka não tem opção
  de manifesto para isso.
- Primeiro build (Nuitka 4.3.4, wxPython 4.3.2): ~37 MB, 19 arquivos, ~40 MB de memória rodando.

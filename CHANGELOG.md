# Changelog

Todas as mudanças relevantes do Lumen ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [1.0.2] - 2026-11-03

### Corrigido

- **Linux:** o app não abria no Ubuntu 24.04 e em distribuições mais novas, por faltar bibliotecas
  do sistema (como `libtiff.so.5`, `libSDL2` e `libnotify`). Agora elas vão dentro do pacote.
- **Linux:** rótulos ("Motor forte") e campos numéricos cortados no GTK, e um retângulo vazio no
  lugar da bateria antes da primeira leitura.

### Interno

- A release só é publicada depois de o pacote Linux rodar em Ubuntu 22.04, Ubuntu 24.04 e Debian 12
  limpos.

## [1.0.1] - 2026-11-03

### Corrigido

- **Linux:** o controle por Bluetooth não era encontrado, porque o acesso usava o backend libusb do
  hidapi; agora usa o hidraw do kernel, que enxerga USB e Bluetooth.

## [1.0.0] - 2026-11-03

Primeira versão pública.

### Adicionado

- **Luz:** cores prontas e seletor de cor, brilho e "Apagar" (no tom mais escuro da cor em uso,
  já que controles paralelos mostram branco com a cor preta).
- **Pisca:** sequência com quantas cores e pausas quiser, cada uma com sua duração; editar, duplicar,
  remover e reordenar arrastando.
- **Vibração:** motores forte e fraco com duração, e padrões de vibração com passos, tocados uma vez
  ou repetindo.
- **Sincronizar com a luz:** pisca e padrão de vibração começam juntos, e recomeçam juntos ao mudar
  o tamanho do ciclo.
- **Bateria:** nível e carregamento no cabeçalho e na dica do ícone da bandeja.
- **Presets:** importar e exportar luz e vibração num arquivo `.lumen.json` (formato próprio,
  versão 1).
- Passo que está tocando destacado em tempo real.
- Bandeja do sistema, instância única e reconexão automática do controle.
- Executáveis para Windows (x64) e Linux (x86_64).

[Não lançado]: https://github.com/bernardoeuler/lumen/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/bernardoeuler/lumen/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/bernardoeuler/lumen/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/bernardoeuler/lumen/releases/tag/v1.0.0

"""Configurações do usuário (última cor, brilho, pisca, vibração), salvas em %LOCALAPPDATA%\\ds4-cli."""
import json
import logging
import os
from pathlib import Path

PASTA_DADOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ds4-cli"
ARQUIVO = PASTA_DADOS / "config.json"

PADRAO = {
    "cor": [0, 0, 255],
    "brilho": 100,         # %
    "piscar": False,
    # passos do pisca, em ciclo: [r, g, b, segundos]; [0, 0, 0, s] é uma pausa apagada
    "sequencia": [[0, 0, 255, 0.5], [0, 0, 0, 0.5]],
    "forte": 255,
    "fraco": 255,
    "duracao": 1.0,        # s
    # padrão de vibração: [forte, fraco, segundos]; [0, 0, s] é uma pausa
    "padrao_vibracao": [[255, 0, 0.3], [0, 0, 0.2], [0, 255, 0.3]],
    "repetir_padrao": False,
}

log = logging.getLogger(__name__)


def carregar():
    dados = dict(PADRAO)
    try:
        # utf-8-sig: aceita também arquivo editado à mão e salvo com BOM (ex.: Notepad, PowerShell)
        salvo = json.loads(ARQUIVO.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return dados
    except (OSError, ValueError) as e:
        log.warning("config inválida, usando padrão (%s)", e)
        return dados
    # só aceita chaves conhecidas com o mesmo tipo do padrão
    for chave, valor in salvo.items():
        if chave in PADRAO and isinstance(valor, type(PADRAO[chave])):
            dados[chave] = valor
    if "sequencia" not in salvo and "aceso" in salvo:
        dados["sequencia"] = _sequencia_antiga(salvo, dados["cor"])
    dados["sequencia"] = [p for p in dados["sequencia"] if _passo_valido(p)]
    dados["padrao_vibracao"] = [p for p in dados["padrao_vibracao"] if _passo_vibracao_valido(p)]
    return dados


def _passo_vibracao_valido(p):
    return (isinstance(p, list) and len(p) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in p[:2])
            and isinstance(p[2], (int, float)) and p[2] > 0)


def _passo_valido(p):
    return (isinstance(p, list) and len(p) == 4
            and all(isinstance(c, int) and 0 <= c <= 255 for c in p[:3])
            and isinstance(p[3], (int, float)) and p[3] > 0)


def _sequencia_antiga(salvo, cor):
    """Converte o pisca da versão anterior (aceso/apagado, com 2ª cor opcional) em sequência."""
    segunda = salvo.get("cor2", [0, 0, 0]) if salvo.get("alternar") else [0, 0, 0]
    return [[*cor, salvo.get("aceso", 0.5)], [*segunda, salvo.get("apagado", 0.5)]]


def salvar(dados):
    try:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        ARQUIVO.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning("não consegui salvar a config (%s)", e)

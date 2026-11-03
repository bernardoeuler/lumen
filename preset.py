"""Preset do Lumen (.lumen.json): luz, pisca e vibração num arquivo só, para importar e exportar.

Formato (versão 1), todas as seções opcionais:

    {
      "format": "lumen-preset", "version": 1, "name": "Alerta",
      "light": {"color": "#00FFFF", "brightness": 100,
                "blink": {"enabled": true, "steps": [{"color": "#FF0000", "duration": 0.5},
                                                     {"off": true, "duration": 0.3}]}},
      "vibration": {"pulse": {"strong": 255, "weak": 255, "duration": 1.0},
                    "pattern": {"repeat": true, "steps": [{"strong": 255, "weak": 0, "duration": 0.3},
                                                          {"off": true, "duration": 0.2}]}},
      "sync": true
    }

Trabalha sobre o mesmo dicionário do config.py (chaves cor, brilho, piscar, sequencia, ...).
"""
import json
import re

FORMATO = "lumen-preset"
VERSAO = 1
EXTENSAO = ".lumen.json"
DURACAO_MIN, DURACAO_MAX = 0.05, 10.0


class PresetInvalido(Exception):
    """O arquivo não é um preset do Lumen (ou está corrompido); nada deve ser aplicado."""


# --- exportar

def _hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def para_preset(cfg, nome):
    """Monta o preset (dicionário pronto para json.dump) a partir das configurações atuais."""
    passos_luz = [{"off": True, "duration": s} if (r, g, b) == (0, 0, 0)
                  else {"color": _hex((r, g, b)), "duration": s}
                  for r, g, b, s in cfg["sequencia"]]
    passos_vib = [{"off": True, "duration": s} if forte == fraco == 0
                  else {"strong": forte, "weak": fraco, "duration": s}
                  for forte, fraco, s in cfg["padrao_vibracao"]]
    return {
        "format": FORMATO,
        "version": VERSAO,
        "name": nome,
        "light": {
            "color": _hex(cfg["cor"]),
            "brightness": cfg["brilho"],
            "blink": {"enabled": cfg["piscar"], "steps": passos_luz},
        },
        "vibration": {
            "pulse": {"strong": cfg["forte"], "weak": cfg["fraco"], "duration": cfg["duracao"]},
            "pattern": {"repeat": cfg["repetir_padrao"], "steps": passos_vib},
        },
        "sync": cfg["sincronizar"],
    }


def salvar(caminho, cfg, nome):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(para_preset(cfg, nome), f, indent=2, ensure_ascii=False)
        f.write("\n")


# --- importar

def _cor(valor):
    if isinstance(valor, str) and re.fullmatch(r"#?[0-9A-Fa-f]{6}", valor.strip()):
        h = valor.strip().lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return None


def _numero(valor, minimo, maximo, inteiro=False):
    """Número limitado à faixa, ou None se não for número (bool não conta)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor = max(minimo, min(maximo, valor))
    return int(round(valor)) if inteiro else round(float(valor), 2)


def _booleano(valor):
    return valor if isinstance(valor, bool) else None


def _passos(lista, converter, avisos, nome):
    if not isinstance(lista, list):
        avisos.append(f"{nome}: 'steps' não é uma lista; ignorado")
        return None
    passos = []
    for i, p in enumerate(lista, 1):
        convertido = converter(p) if isinstance(p, dict) else None
        if convertido is None:
            avisos.append(f"{nome}: passo {i} inválido; descartado")
        else:
            passos.append(convertido)
    if not passos:
        avisos.append(f"{nome}: nenhum passo válido; mantido o atual")
        return None
    return passos


def _passo_luz(p):
    s = _numero(p.get("duration"), DURACAO_MIN, DURACAO_MAX)
    if s is None:
        return None
    if p.get("off") is True:
        return [0, 0, 0, s]
    cor = _cor(p.get("color"))
    return [*cor, s] if cor else None


def _passo_vibracao(p):
    s = _numero(p.get("duration"), DURACAO_MIN, DURACAO_MAX)
    if s is None:
        return None
    if p.get("off") is True:
        return [0, 0, s]
    forte = _numero(p.get("strong", 0), 0, 255, inteiro=True)
    fraco = _numero(p.get("weak", 0), 0, 255, inteiro=True)
    if forte is None or fraco is None:
        return None
    return [forte, fraco, s]


def de_preset(dados):
    """Converte um preset nas mudanças para as configurações: (mudancas, nome, avisos).

    Só vem em `mudancas` o que o arquivo trouxe e for válido; o resto fica como está.
    Lança PresetInvalido se não for um preset do Lumen.
    """
    if not isinstance(dados, dict) or dados.get("format") != FORMATO:
        raise PresetInvalido("o arquivo não é um preset do Lumen")
    versao = dados.get("version")
    if isinstance(versao, bool) or not isinstance(versao, int) or versao < 1:
        raise PresetInvalido("versão do preset ausente ou inválida")
    avisos = []
    if versao > VERSAO:
        avisos.append(f"preset da versão {versao} (este app lê a {VERSAO}); importado o que foi reconhecido")

    m = {}

    def pegar(chave, valor):
        if valor is not None:
            m[chave] = valor

    luz = dados.get("light")
    if isinstance(luz, dict):
        if "color" in luz:
            cor = _cor(luz["color"])
            if cor:
                m["cor"] = cor
            else:
                avisos.append("light.color inválida; mantida a atual")
        pegar("brilho", _numero(luz.get("brightness"), 1, 100, inteiro=True))
        pisca = luz.get("blink")
        if isinstance(pisca, dict):
            pegar("piscar", _booleano(pisca.get("enabled")))
            if "steps" in pisca:
                pegar("sequencia", _passos(pisca["steps"], _passo_luz, avisos, "light.blink"))

    vib = dados.get("vibration")
    if isinstance(vib, dict):
        pulso = vib.get("pulse")
        if isinstance(pulso, dict):
            pegar("forte", _numero(pulso.get("strong"), 0, 255, inteiro=True))
            pegar("fraco", _numero(pulso.get("weak"), 0, 255, inteiro=True))
            pegar("duracao", _numero(pulso.get("duration"), 0.1, 10.0))
        padrao = vib.get("pattern")
        if isinstance(padrao, dict):
            pegar("repetir_padrao", _booleano(padrao.get("repeat")))
            if "steps" in padrao:
                pegar("padrao_vibracao", _passos(padrao["steps"], _passo_vibracao, avisos, "vibration.pattern"))

    pegar("sincronizar", _booleano(dados.get("sync")))
    if not m:
        raise PresetInvalido("o preset não tem nenhuma configuração válida")
    nome = dados.get("name") if isinstance(dados.get("name"), str) else None
    return m, nome, avisos


def carregar(caminho):
    """Lê o arquivo e devolve (mudancas, nome, avisos); PresetInvalido se não der."""
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            dados = json.load(f)
    except (OSError, ValueError) as e:
        raise PresetInvalido(f"não consegui ler o arquivo ({e})") from e
    return de_preset(dados)

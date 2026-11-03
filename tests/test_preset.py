import json

import pytest

import config
import preset

CFG = dict(
    config.PADRAO,
    cor=[0, 255, 255],
    sequencia=[[255, 0, 0, 0.5], [0, 0, 0, 0.3]],
    padrao_vibracao=[[255, 0, 0.3], [0, 0, 0.2]],
    piscar=True,
    repetir_padrao=True,
    sincronizar=True,
)


def base(**secoes):
    return {"format": preset.FORMATO, "version": preset.VERSAO, **secoes}


def test_ida_e_volta_preserva_tudo(tmp_path):
    arquivo = tmp_path / f"teste{preset.EXTENSAO}"
    preset.salvar(arquivo, CFG, "teste")
    mudancas, nome, avisos = preset.carregar(arquivo)
    assert nome == "teste"
    assert avisos == []
    assert set(mudancas) == set(config.PADRAO)
    assert all(mudancas[k] == CFG[k] for k in mudancas)


def test_pausas_viram_off():
    dados = preset.para_preset(CFG, "x")
    assert dados["light"]["blink"]["steps"][1] == {"off": True, "duration": 0.3}
    assert dados["vibration"]["pattern"]["steps"][1] == {"off": True, "duration": 0.2}
    json.dumps(dados)  # serializável


@pytest.mark.parametrize("dados", [
    {"foo": 1},
    {"format": "outro", "version": 1},
    {"format": preset.FORMATO},
    {"format": preset.FORMATO, "version": "1"},
    {"format": preset.FORMATO, "version": True},
    [],
])
def test_recusa_o_que_nao_e_preset(dados):
    with pytest.raises(preset.PresetInvalido):
        preset.de_preset(dados)


def test_recusa_preset_sem_nada_valido():
    with pytest.raises(preset.PresetInvalido):
        preset.de_preset(base(light={"color": "azul"}))


def test_recusa_json_quebrado(tmp_path):
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text("{ isso não é json", encoding="utf-8")
    with pytest.raises(preset.PresetInvalido):
        preset.carregar(arquivo)


def test_secoes_sao_opcionais():
    mudancas, _, _ = preset.de_preset(base(light={"color": "#ff8800"}))
    assert mudancas == {"cor": [255, 136, 0]}


def test_limita_valores_e_descarta_passos_ruins():
    passos = [{"strong": 300, "weak": -5, "duration": 99}, {"off": True, "duration": 0.2},
              {"strong": "x", "duration": 1}, 5]
    mudancas, _, avisos = preset.de_preset(base(vibration={"pattern": {"steps": passos}}))
    assert mudancas["padrao_vibracao"] == [[255, 0, preset.DURACAO_MAX], [0, 0, 0.2]]
    assert len(avisos) == 2


def test_versao_futura_importa_com_aviso():
    dados = base(light={"brightness": 50})
    dados["version"] = preset.VERSAO + 1
    mudancas, _, avisos = preset.de_preset(dados)
    assert mudancas == {"brilho": 50}
    assert any("versão" in a for a in avisos)


def test_aceita_bom_do_bloco_de_notas(tmp_path):
    arquivo = tmp_path / "bom.json"
    arquivo.write_text(json.dumps(base(sync=False)), encoding="utf-8-sig")
    mudancas, _, _ = preset.carregar(arquivo)
    assert mudancas == {"sincronizar": False}

"""Testes da janela: abre de verdade, mexe nos controles como o usuário e confere o que chega ao
controle (o Gerenciador real, sem a thread: o estado fica em g._estado).

No Linux sem tela, rodar com um display virtual: xvfb-run -a python -m pytest
"""
import pytest

wx = pytest.importorskip("wx")

import app  # noqa: E402
import config  # noqa: E402
import preset  # noqa: E402
from gerenciador import Gerenciador  # noqa: E402

AZUL, VERMELHO = (0, 0, 255), (255, 0, 0)


# --- infraestrutura

@pytest.fixture(scope="session")
def wxapp():
    app.declarar_dpi()
    return wx.App(False)


@pytest.fixture
def salvos(monkeypatch):
    """Configurações que a janela mandou salvar (nada vai para o disco)."""
    lista = []
    monkeypatch.setattr(config, "salvar", lambda dados: lista.append(dict(dados)))
    return lista


@pytest.fixture
def janela(wxapp, salvos):
    cfg = dict(config.PADRAO, cor=list(AZUL), sequencia=[[*AZUL, 0.5], [0, 0, 0, 0.5]],
               padrao_vibracao=[[255, 0, 0.3], [0, 0, 0.2]])
    j = app.Janela(Gerenciador(), cfg)
    j.Show()
    processar()
    yield j
    for editor in (j.ed_cores, j.ed_vib):
        if editor.detalhe:
            editor.detalhe.fechar()
    j.sair()
    processar()


def processar():
    wx.GetApp().ProcessPendingEvents()
    wx.Yield()


def estado(j):
    return j.g._estado


def _disparar(ctrl, tipo, **campos):
    ev = wx.CommandEvent(tipo, ctrl.GetId())
    ev.SetEventObject(ctrl)
    if "inteiro" in campos:
        ev.SetInt(campos["inteiro"])
    if "texto" in campos:
        ev.SetString(campos["texto"])
    ctrl.GetEventHandler().ProcessEvent(ev)
    processar()


def clicar(botao):
    _disparar(botao, wx.wxEVT_BUTTON)


def marcar(caixa, valor=True):
    caixa.SetValue(valor)
    _disparar(caixa, wx.wxEVT_CHECKBOX, inteiro=int(valor))


def alternar(botao, valor):
    botao.SetValue(valor)
    _disparar(botao, wx.wxEVT_TOGGLEBUTTON, inteiro=int(valor))


def mover(slider, valor):
    slider.SetValue(valor)
    _disparar(slider, wx.wxEVT_SLIDER, inteiro=valor)


def digitar(campo, texto):
    _disparar(campo, wx.wxEVT_TEXT, texto=texto)


def clicar_bolinha(bolinha):
    ev = wx.MouseEvent(wx.wxEVT_LEFT_UP)
    ev.SetEventObject(bolinha)
    bolinha.GetEventHandler().ProcessEvent(ev)
    processar()


def campos_do_detalhe(editor, tipo):
    painel = editor.detalhe.GetChildren()[0]
    return [c for c in painel.GetChildren() if isinstance(c, tipo)]


# --- abrir

def test_abre_a_janela(janela):
    assert janela.IsShown()
    assert janela.GetTitle() == app.TITULO
    assert not janela.bateria.IsShown()  # sem leitura, a bateria não aparece
    assert estado(janela).rgb == AZUL  # a cor salva já vai para o controle ao abrir


def test_bateria_aparece_na_primeira_leitura(janela):
    janela._mostrar_bateria(70, True)
    assert janela.bateria.IsShown()
    assert "70%" in janela.bateria.GetToolTipText()
    janela._mostrar_bateria(None, False)
    assert not janela.bateria.IsShown()


def test_status_da_conexao(janela):
    janela._mostrar_conexao(True, True)
    assert "Bluetooth" in janela.status.GetLabel()
    janela._mostrar_conexao(False, None)
    assert "desconectado" in janela.status.GetLabel()


# --- luz

def test_clicar_numa_cor_pronta_muda_a_luz(janela):
    vermelha = next(b for b in janela.bolinhas if b.rgb == VERMELHO)
    clicar_bolinha(vermelha)
    assert estado(janela).rgb == VERMELHO
    assert vermelha.selecionada
    assert janela.hex.GetLabel() == "#FF0000"


def test_brilho_pelo_slider_e_pelo_campo(janela):
    mover(janela.slider_brilho, 50)
    assert estado(janela).rgb == app.com_brilho(AZUL, 50)
    assert janela.slider_brilho.campo.GetValue() == 50  # o campo acompanha o slider


def test_apagar_e_acender(janela):
    alternar(janela.bt_ligar, True)
    assert estado(janela).rgb == app.tom_apagado(AZUL)  # o clone mostra branco com (0, 0, 0)
    assert janela.bt_ligar.GetLabel() == "Acender"
    alternar(janela.bt_ligar, False)
    assert estado(janela).rgb == AZUL
    assert janela.bt_ligar.GetLabel() == "Apagar"


# --- pisca

def test_piscar_liga_e_desliga(janela):
    marcar(janela.chk_piscar, True)
    e = estado(janela)
    assert e.pisca_inicio is not None
    # a pausa vai como o tom apagado da cor anterior
    assert e.passos == [(AZUL, 0.5), (app.tom_apagado(AZUL), 0.5)]
    marcar(janela.chk_piscar, False)
    assert estado(janela).pisca_inicio is None


def test_adicionar_duplicar_e_remover_passos(janela):
    janela.ed_cores.adicionar([*VERMELHO, 0.25])
    assert [p[0] for p in estado(janela).passos][-1] == VERMELHO
    janela.ed_cores.duplicar(0)
    assert len(janela.passos) == 4 and janela.passos[1] == janela.passos[0]
    janela.ed_cores.remover(0)
    assert len(estado(janela).passos) == 3


def test_arrastar_muda_a_ordem(janela):
    janela.ed_cores.adicionar([*VERMELHO, 0.25])
    janela.ed_cores.arrastar(2, 0)  # o vermelho vai para o começo
    assert janela.passos[0][:3] == list(VERMELHO)
    assert estado(janela).passos[0][0] == VERMELHO


def test_digitar_duracao_no_detalhe(janela):
    janela.ed_cores.abrir_detalhe(0)
    processar()
    assert janela.ed_cores.detalhe is not None
    duracao = campos_do_detalhe(janela.ed_cores, wx.SpinCtrlDouble)[0]
    digitar(duracao, "1.25")
    assert janela.passos[0][3] == 1.25
    assert estado(janela).passos[0][1] == 1.25
    digitar(duracao, "abc")  # valor inválido é ignorado
    assert janela.passos[0][3] == 1.25


# --- vibração

def test_vibrar_e_parar_pelo_mesmo_botao(janela):
    clicar(janela.bt_vibrar)
    assert janela.g.andamento()[2] is True
    assert janela.bt_vibrar.GetLabel() == "Parar"
    clicar(janela.bt_vibrar)
    assert janela.g.andamento()[2] is False
    assert janela.bt_vibrar.GetLabel() == janela.ROTULO_VIBRAR


def test_tocar_padrao(janela):
    clicar(janela.bt_tocar)
    e = estado(janela)
    assert e.padrao_inicio is not None
    assert e.padrao == [(255, 0, 0.3), (0, 0, 0.2)]
    assert janela.bt_tocar.GetLabel() == "Parar"
    clicar(janela.bt_tocar)
    assert estado(janela).padrao_inicio is None


def test_digitar_intensidade_no_detalhe_da_vibracao(janela):
    janela.ed_vib.abrir_detalhe(0)
    processar()
    forte = campos_do_detalhe(janela.ed_vib, wx.SpinCtrl)[0]
    digitar(forte, "123")
    assert janela.padrao[0][0] == 123
    assert estado(janela).padrao[0][0] == 123


# --- sincronizar

def test_sincronizar_comeca_junto_ao_ligar_o_pisca(janela):
    marcar(janela.chk_sincronizar, True)
    marcar(janela.chk_piscar, True)
    e = estado(janela)
    assert e.pisca_inicio is not None and e.pisca_inicio == e.padrao_inicio


def test_sincronizar_recomeca_junto_ao_mudar_o_ciclo(janela):
    marcar(janela.chk_piscar, True)
    janela.g.tocar_padrao(True)  # desalinhado do pisca
    marcar(janela.chk_sincronizar, True)
    janela.ed_vib.adicionar([100, 100, 0.3])
    e = estado(janela)
    assert e.pisca_inicio == e.padrao_inicio


def test_sem_sincronizar_nao_mexe_no_alinhamento(janela):
    marcar(janela.chk_piscar, True)
    janela.g.tocar_padrao(True)
    antes = estado(janela).padrao_inicio - estado(janela).pisca_inicio
    janela.ed_cores.adicionar([*VERMELHO, 0.5])
    assert estado(janela).padrao_inicio - estado(janela).pisca_inicio == antes


# --- presets e configurações

def test_importar_preset_aplica_na_tela_e_no_controle(janela):
    mudancas, _, _ = preset.de_preset({
        "format": preset.FORMATO, "version": 1,
        "light": {"color": "#FF0000", "brightness": 40,
                  "blink": {"enabled": True, "steps": [{"color": "#00FF00", "duration": 0.2}]}},
        "vibration": {"pattern": {"repeat": True, "steps": [{"strong": 10, "weak": 20, "duration": 0.4}]}},
    })
    janela.aplicar_preset(mudancas)
    processar()
    assert janela.cor == VERMELHO and janela.slider_brilho.GetValue() == 40
    assert janela.slider_brilho.campo.GetValue() == 40
    assert janela.chk_piscar.IsChecked() and janela.chk_repetir.IsChecked()
    assert janela.ed_cores.itens is janela.passos  # a faixa continua ligada à lista
    e = estado(janela)
    assert e.passos == [(app.com_brilho((0, 255, 0), 40), 0.2)]
    assert e.padrao == [(10, 20, 0.4)]


def test_salva_o_que_esta_na_tela(janela, salvos):
    mover(janela.slider_forte, 100)
    marcar(janela.chk_repetir, True)
    janela.salvar_config()
    ultimo = salvos[-1]
    assert ultimo["forte"] == 100 and ultimo["repetir_padrao"] is True
    assert ultimo["cor"] == list(AZUL)

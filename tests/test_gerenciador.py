import time

from gerenciador import Estado, Gerenciador


def estado_com_padrao(repetir):
    e = Estado()
    e.padrao = [(255, 0, 0.3), (0, 0, 0.2), (0, 200, 0.5)]
    e.padrao_inicio, e.padrao_repetir = 0.0, repetir
    return e


def test_padrao_uma_vez_para_no_fim():
    e = estado_com_padrao(repetir=False)
    assert [e.saida(t)[1:] for t in (0.1, 0.4, 0.6)] == [(255, 0), (0, 0), (0, 200)]
    assert e.saida(1.1)[1:] == (0, 0)
    assert e.padrao_inicio is None


def test_padrao_repetindo_volta_ao_inicio():
    e = estado_com_padrao(repetir=True)
    assert e.saida(1.1)[1:] == (255, 0)
    assert e.padrao_inicio == 0.0


def test_passo_da_sequencia_em_ciclo():
    e = Estado()
    e.passos = [((1, 2, 3), 0.5), ((0, 0, 0), 0.5)]
    e.pisca_inicio = 0.0
    assert [e.passo_da_sequencia(t) for t in (0.2, 0.7, 1.2)] == [0, 1, 0]
    assert e.cor_da_sequencia(0.7) == (0, 0, 0)


def test_sem_pisca_usa_a_cor_fixa():
    e = Estado()
    e.rgb = (9, 9, 9)
    e.passos = [((1, 2, 3), 0.5)]
    assert e.passo_da_sequencia(1.0) is None
    assert e.saida(1.0)[0] == (9, 9, 9)


def test_tocar_padrao_com_pisca_comeca_junto():
    g = Gerenciador()  # sem iniciar a thread: só o estado
    g.sequencia([((255, 0, 0), 0.5)])
    g.padrao_vibracao([(255, 0, 0.3)])
    g.piscar()
    time.sleep(0.05)
    g.tocar_padrao(True, com_pisca=False)
    assert g._estado.padrao_inicio != g._estado.pisca_inicio
    g.tocar_padrao(True, com_pisca=True)
    assert g._estado.padrao_inicio == g._estado.pisca_inicio


def test_tocar_padrao_com_pisca_nao_liga_o_pisca():
    g = Gerenciador()
    g.padrao_vibracao([(255, 0, 0.3)])
    g.tocar_padrao(False, com_pisca=True)
    assert g._estado.pisca_inicio is None


def test_vibrar_cancela_o_padrao():
    g = Gerenciador()
    g.padrao_vibracao([(255, 0, 0.3)])
    g.tocar_padrao(True)
    g.vibrar(100, 100, 1.0)
    assert g._estado.padrao_inicio is None
    assert g.andamento()[2] is True

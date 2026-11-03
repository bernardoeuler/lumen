"""Protocolo do controle (controle.py) e o Gerenciador de verdade, contra o controle falso (clone).

Roda igual no Windows e no Linux: só o acesso HID é falso. Os cenários vêm do que foi descoberto à
mão com o controle real (CLAUDE.md, "Particularidades do controle").
"""
import time
import zlib

import pytest

import controle
from ds4_falso import BRANCO, ControleClone
from gerenciador import Gerenciador

VERDE, AZUL = (0, 255, 0), (0, 0, 255)


def esperar(condicao, limite=3.0):
    """Espera a thread do gerenciador chegar no estado esperado."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()


# --- achar e abrir

def test_acha_so_o_ds4(hid_falso):
    hid_falso.plugar(ControleClone(pid=0x0CE6, caminho=b"dualsense"))  # outro controle da Sony
    assert controle.find_controller() is None
    hid_falso.plugar(ControleClone())
    assert controle.find_controller()["product_id"] == 0x09CC


def test_sem_controle_avisa(hid_falso):
    with pytest.raises(controle.ControleNaoEncontrado):
        controle.DS4()


@pytest.mark.parametrize("estilo,bluetooth", [("windows", True), ("windows", False),
                                              ("linux", True), ("linux", False)])
def test_detecta_bluetooth_no_windows_e_no_linux(hid_falso, estilo, bluetooth):
    # o Windows identifica pelo GUID do perfil HID no caminho; o Linux, pelo bus_type
    hid_falso.plugar(ControleClone(bluetooth=bluetooth, estilo=estilo))
    assert controle.DS4().bluetooth is bluetooth


# --- relatório de saída

def test_relatorio_bluetooth(hid_falso):
    clone = hid_falso.plugar(ControleClone())
    controle.DS4().send(VERDE, forte=200, fraco=50)
    rep = clone.ultimo()
    assert rep is not None and not clone.rejeitados
    assert len(rep) == 78 and rep[:4] == bytes([0x11, 0xC0, 0x00, 0x07])
    assert rep[-4:] == zlib.crc32(b"\xa2" + rep[:-4]).to_bytes(4, "little")
    assert clone.luz == VERDE
    assert clone.motores == (200, 50)


def test_relatorio_usb(hid_falso):
    clone = hid_falso.plugar(ControleClone(bluetooth=False))
    controle.DS4().send(AZUL, forte=10, fraco=20)
    rep = clone.ultimo()
    assert len(rep) == 32 and rep[0] == 0x05 and rep[1] == 0x07
    assert clone.luz == AZUL and clone.motores == (10, 20)


def test_luz_exige_as_tres_flags(hid_falso):
    # mania do clone: só a flag da luz (0x02) é ignorada; por isso o app sempre manda 0x07
    clone = hid_falso.plugar(ControleClone())
    ds4 = controle.DS4()
    ds4.send(VERDE, flags=controle.FLAG_LIGHT)
    assert clone.luz is None
    ds4.send(VERDE)
    assert clone.luz == VERDE


def test_preto_nao_vira_branco(hid_falso):
    # o clone mostra branco com (0, 0, 0); o controle.py troca pelo tom mais escuro possível
    clone = hid_falso.plugar(ControleClone())
    controle.DS4().send((0, 0, 0))
    assert clone.luz != BRANCO
    assert clone.luz == controle.COR_APAGADA


def test_falha_de_envio_vira_erro(hid_falso):
    clone = hid_falso.plugar(ControleClone())
    ds4 = controle.DS4()
    clone.desconectar()
    with pytest.raises(OSError):
        ds4.send(VERDE)


# --- bateria

@pytest.mark.parametrize("bluetooth", [True, False])
@pytest.mark.parametrize("status,esperado", [(0x0A, (100, False)), (0x05, (50, False)),
                                             (0x00, (0, False)), (0x15, (50, True)),
                                             (0x1B, (100, True))])  # 11 = cheia carregando
def test_bateria(hid_falso, bluetooth, status, esperado):
    clone = hid_falso.plugar(ControleClone(bluetooth=bluetooth))
    clone.status_bateria = status
    ds4 = controle.DS4()
    assert ds4.ler_bateria() is None  # o clone só manda entrada depois de receber saída
    ds4.send(VERDE)
    assert ds4.ler_bateria() == esperado


# --- o gerenciador de verdade, com a thread

@pytest.fixture
def gerenciador(hid_falso):
    eventos = {"conexao": [], "bateria": []}
    g = Gerenciador(ao_mudar_conexao=lambda c, bt: eventos["conexao"].append((c, bt)),
                    ao_mudar_bateria=lambda p, cabo: eventos["bateria"].append((p, cabo)))
    g.eventos = eventos
    yield g
    g.encerrar()


def test_conecta_e_aplica_a_luz(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    gerenciador.luz(VERDE)
    gerenciador.iniciar()
    assert esperar(lambda: clone.luz == VERDE)
    assert gerenciador.eventos["conexao"][0] == (True, True)


def test_le_a_bateria(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    clone.status_bateria = 0x13  # 30%, no cabo
    gerenciador.iniciar()
    assert esperar(lambda: (30, True) in gerenciador.eventos["bateria"])


def test_vibracao_para_sozinha(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    gerenciador.iniciar()
    gerenciador.vibrar(255, 128, 0.2)
    assert esperar(lambda: clone.motores == (255, 128))
    assert esperar(lambda: clone.motores == (0, 0))


def test_pisca_por_software(hid_falso, gerenciador):
    # o clone ignora o pisca por hardware: as cores precisam chegar uma a uma
    clone = hid_falso.plugar(ControleClone())
    vistas = set()
    gerenciador.sequencia([(VERDE, 0.1), (AZUL, 0.1)])
    gerenciador.piscar()
    gerenciador.iniciar()
    assert esperar(lambda: vistas.add(clone.luz) or {VERDE, AZUL} <= vistas)


def test_padrao_de_vibracao(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    vistos = set()
    gerenciador.padrao_vibracao([(255, 0, 0.1), (0, 200, 0.1)])
    gerenciador.iniciar()
    gerenciador.tocar_padrao(repetir=False)
    assert esperar(lambda: vistos.add(clone.motores) or {(255, 0), (0, 200)} <= vistos)
    assert esperar(lambda: clone.motores == (0, 0))  # tocado uma vez, para no fim


def test_keepalive_reenvia_sem_mudanca(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    gerenciador.luz(VERDE)
    gerenciador.iniciar()
    assert esperar(lambda: clone.recebidos)
    antes = len(clone.recebidos)
    assert esperar(lambda: len(clone.recebidos) > antes, limite=2.5)  # KEEPALIVE = 1 s


def test_reconecta_e_restaura_o_estado(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    gerenciador.luz(VERDE)
    gerenciador.iniciar()
    assert esperar(lambda: clone.luz == VERDE)

    clone.desconectar()  # ex.: bateria acabou
    assert esperar(lambda: (False, None) in gerenciador.eventos["conexao"])
    assert (None, False) in gerenciador.eventos["bateria"]  # a bateria some da tela

    clone.luz = None
    gerenciador.luz(AZUL)  # mudou enquanto estava desconectado
    clone.reconectar()
    assert esperar(lambda: gerenciador.eventos["conexao"].count((True, True)) == 2, limite=4)
    assert esperar(lambda: clone.luz == AZUL)


def test_encerrar_para_os_motores_e_mantem_a_cor(hid_falso, gerenciador):
    clone = hid_falso.plugar(ControleClone())
    gerenciador.luz(VERDE)
    gerenciador.iniciar()
    gerenciador.vibrar(255, 255, 10)
    assert esperar(lambda: clone.motores == (255, 255))
    gerenciador.encerrar()
    assert clone.motores == (0, 0)
    assert clone.luz == VERDE

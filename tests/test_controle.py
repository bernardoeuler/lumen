import sys

import pytest

import controle


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="só no Linux")
def test_linux_usa_hidraw():
    # o backend "hid" (libusb) do wheel não enxerga controles Bluetooth
    assert controle.hid.__name__ == "hidraw"


def test_enumerar_nao_falha():
    # sem controle conectado (CI), só não pode quebrar
    assert controle.find_controller() is None or "path" in controle.find_controller()

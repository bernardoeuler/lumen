import pytest

import controle
from ds4_falso import HidFalso


@pytest.fixture
def hid_falso(monkeypatch):
    """Troca o acesso HID do controle.py pelo controle falso (sem hardware)."""
    falso = HidFalso()
    monkeypatch.setattr(controle, "hid", falso)
    return falso

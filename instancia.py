"""Instância única: a primeira instância fica ouvindo; uma instância nova avisa a que já está rodando
(ex.: "mostrar") e encerra, sem tocar no controle.

Windows: named pipe (instancia_windows.py). Linux: socket Unix abstrato (instancia_unix.py).
As duas expõem Instancia (com .principal e .ouvir(ao_receber)) e avisar(mensagem) -> bool.
"""
import sys

if sys.platform == "win32":
    from instancia_windows import Instancia, avisar  # noqa: F401
else:
    from instancia_unix import Instancia, avisar  # noqa: F401

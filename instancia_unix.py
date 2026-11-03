"""Instância única no Linux, via socket Unix abstrato (usado pelo instancia.py).

O endereço abstrato (começa com \\0) não cria arquivo e some sozinho quando o processo termina, então
não sobra "trava" velha depois de um encerramento forçado.
"""
import getpass
import logging
import socket
import threading

log = logging.getLogger(__name__)

ENDERECO = f"\0lumen-{getpass.getuser()}"


def avisar(mensagem, espera_ms=2000):
    """Manda a mensagem para a instância que já está rodando. Devolve True se conseguiu."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(espera_ms / 1000)
            s.connect(ENDERECO)
            s.sendall(mensagem.encode("utf-8"))
        return True
    except OSError:
        return False


class Instancia:
    """Tenta ser a instância principal; se for, ouvir() repassa as mensagens recebidas."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._sock.bind(ENDERECO)
        except OSError:
            # endereço em uso: já existe uma instância rodando
            self._sock.close()
            self._sock = None
        else:
            self._sock.listen(4)
        self.principal = self._sock is not None

    def ouvir(self, ao_receber):
        """Chama ao_receber(mensagem) numa thread própria a cada mensagem."""
        self._ao_receber = ao_receber
        threading.Thread(target=self._loop, name="instancia", daemon=True).start()

    def _loop(self):
        while True:
            try:
                conexao, _ = self._sock.accept()
                with conexao:
                    conexao.settimeout(2)
                    dados = conexao.recv(512)
            except OSError as e:
                log.warning("falha ao receber mensagem de outra instância (%s)", e)
                continue
            if dados:
                self._ao_receber(dados.decode("utf-8", errors="replace"))

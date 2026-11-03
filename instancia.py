"""Instância única via named pipe do Windows.

A primeira instância cria o pipe e fica ouvindo. Uma instância nova que encontra o pipe já existente
manda uma mensagem por ele (ex.: "mostrar") e encerra, sem tocar no controle.
"""
import ctypes
import getpass
import logging
import threading
from ctypes import wintypes

log = logging.getLogger(__name__)

NOME_PIPE = rf"\\.\pipe\faisca-{getpass.getuser()}"

PIPE_ACCESS_INBOUND = 0x00000001
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
PIPE_UNLIMITED_INSTANCES = 255
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
ERROR_ACCESS_DENIED = 5
ERROR_PIPE_BUSY = 231
ERROR_PIPE_CONNECTED = 535
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateNamedPipeW.restype = wintypes.HANDLE
k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
k32.ConnectNamedPipe.restype = wintypes.BOOL
k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
k32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def _criar_instancia(primeira):
    modo = PIPE_ACCESS_INBOUND | (FILE_FLAG_FIRST_PIPE_INSTANCE if primeira else 0)
    h = k32.CreateNamedPipeW(NOME_PIPE, modo, PIPE_TYPE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
                             PIPE_UNLIMITED_INSTANCES, 0, 512, 0, None)
    if h == INVALID_HANDLE_VALUE:
        return None, ctypes.get_last_error()
    return h, 0


def avisar(mensagem, espera_ms=2000):
    """Manda a mensagem para a instância que já está rodando. Devolve True se conseguiu."""
    for _ in range(2):
        h = k32.CreateFileW(NOME_PIPE, GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        if h != INVALID_HANDLE_VALUE:
            dados = mensagem.encode("utf-8")
            escritos = wintypes.DWORD()
            ok = k32.WriteFile(h, dados, len(dados), ctypes.byref(escritos), None)
            k32.CloseHandle(h)
            return bool(ok)
        if ctypes.get_last_error() != ERROR_PIPE_BUSY or not k32.WaitNamedPipeW(NOME_PIPE, espera_ms):
            return False
    return False


class Instancia:
    """Tenta ser a instância principal; se for, ouvir() repassa as mensagens recebidas."""

    def __init__(self):
        self._ao_receber = None
        self._h, erro = _criar_instancia(primeira=True)
        if self._h is None and erro != ERROR_ACCESS_DENIED:
            raise OSError(erro, f"CreateNamedPipeW falhou ({erro})")
        self.principal = self._h is not None

    def ouvir(self, ao_receber):
        """Chama ao_receber(mensagem) numa thread própria a cada mensagem."""
        self._ao_receber = ao_receber
        threading.Thread(target=self._loop, name="pipe", daemon=True).start()

    def _loop(self):
        h = self._h
        buf = ctypes.create_string_buffer(512)
        while True:
            if not k32.ConnectNamedPipe(h, None) and ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                log.warning("ConnectNamedPipe falhou (%s)", ctypes.get_last_error())
            lidos = wintypes.DWORD()
            ok = k32.ReadFile(h, buf, len(buf), ctypes.byref(lidos), None)
            mensagem = buf.raw[:lidos.value].decode("utf-8", errors="replace") if ok else ""
            # cria a próxima instância antes de fechar esta, para o pipe nunca deixar de existir
            # (senão uma instância nova poderia se achar a primeira nesse intervalo)
            proximo, erro = _criar_instancia(primeira=False)
            k32.DisconnectNamedPipe(h)
            k32.CloseHandle(h)
            if proximo is None:
                log.error("não consegui recriar o pipe (%s); instância única desativada", erro)
                return
            h = proximo
            if mensagem:
                self._ao_receber(mensagem)

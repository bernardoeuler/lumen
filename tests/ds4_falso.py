"""Controle de PS4 falso, para testar o protocolo sem hardware (Windows e Linux).

Substitui o módulo `hid` usado pelo controle.py (veja a fixture `hid_falso` no conftest.py) e se
comporta como o controle paralelo (clone) do projeto, com as manias descobertas à mão:

- só aplica a luz se o relatório trouxer as três flags juntas (0x07);
- mostra BRANCO quando recebe a cor (0, 0, 0);
- ignora o pisca por hardware (bytes de aceso/apagado);
- no Bluetooth, confere o CRC32 e descarta relatório com CRC errado;
- só manda relatórios de entrada (com a bateria) depois de receber um de saída.
"""
import threading
import zlib

SONY = 0x054C
DS4_V2 = 0x09CC
BRANCO = (255, 255, 255)


class ControleClone:
    """O controle em si: guarda o que ele mostraria/faria com os relatórios recebidos."""

    def __init__(self, bluetooth=True, pid=DS4_V2, caminho=None, estilo="windows"):
        self.bluetooth = bluetooth
        self.pid = pid
        self.caminho = caminho or self._caminho_padrao(estilo)
        self.estilo = estilo
        self.luz = None             # cor que a barra de luz mostra
        self.motores = (0, 0)       # (forte, fraco)
        self.recebidos = []         # relatórios de saída aceitos, em ordem
        self.rejeitados = []        # relatórios descartados (CRC ou formato errado)
        self.status_bateria = 0x0A  # byte de status: nível nos 4 bits de baixo, 0x10 = cabo
        self.conectado = True
        self.ja_recebeu_saida = False
        self._trava = threading.Lock()

    def _caminho_padrao(self, estilo):
        if estilo == "windows":
            guid = "00001124-0000-1000-8000-00805f9b34fb" if self.bluetooth else "usb"
            return f"\\\\?\\hid#{{{guid}}}_vid&0002054c_pid&{self.pid:04x}#abc".encode()
        return b"/dev/hidraw3"

    def info(self):
        """O dicionário que o hid.enumerate() devolveria para este controle."""
        if self.estilo == "windows":
            bus = 0  # o Windows nem sempre informa; o controle.py olha o caminho
        else:
            bus = 2 if self.bluetooth else 1  # HID_API_BUS_BLUETOOTH / HID_API_BUS_USB
        return {"vendor_id": SONY, "product_id": self.pid, "path": self.caminho, "bus_type": bus,
                "product_string": "Wireless Controller"}

    # --- o que chega do app

    def receber(self, dados):
        dados = bytes(dados)
        with self._trava:
            if not self.conectado:
                return -1
            if self.bluetooth:
                if len(dados) != 78 or dados[0] != 0x11:
                    self.rejeitados.append(dados)
                    return len(dados)
                crc = zlib.crc32(b"\xa2" + dados[:-4]).to_bytes(4, "little")
                if dados[-4:] != crc:
                    self.rejeitados.append(dados)  # o controle real ignora em silêncio
                    return len(dados)
                flags, base = dados[3], 6
                if dados[1] != 0xC0 or dados[2] != 0x00:
                    self.rejeitados.append(dados)
                    return len(dados)
            else:
                if len(dados) != 32 or dados[0] != 0x05:
                    self.rejeitados.append(dados)
                    return len(dados)
                flags, base = dados[1], 4
            self.recebidos.append(dados)
            self.ja_recebeu_saida = True
            if flags & 0x01:
                self.motores = (dados[base + 1], dados[base])
            if flags == 0x07:  # mania do clone: luz só com as três flags juntas
                cor = tuple(dados[base + 2:base + 5])
                self.luz = BRANCO if cor == (0, 0, 0) else cor  # e preto vira branco
            return len(dados)

    def relatorio_de_entrada(self):
        """Próximo relatório de entrada (com a bateria), ou None se o controle ainda não manda."""
        with self._trava:
            if not self.conectado or not self.ja_recebeu_saida:
                return None
            if self.bluetooth:
                rep = bytearray(78)
                rep[0], rep[1] = 0x11, 0xC0
                rep[32] = self.status_bateria
            else:
                rep = bytearray(64)
                rep[0] = 0x01
                rep[30] = self.status_bateria
            return list(rep)

    def ultimo(self):
        with self._trava:
            return self.recebidos[-1] if self.recebidos else None

    def desconectar(self):
        with self._trava:
            self.conectado = False

    def reconectar(self):
        with self._trava:
            self.conectado = True
            self.ja_recebeu_saida = False


class _Dispositivo:
    """O "hid.device()" aberto pelo app."""

    def __init__(self, hid):
        self._hid = hid
        self._controle = None
        self._entradas_por_leitura = 1

    def open_path(self, caminho):
        controle = self._hid.por_caminho(caminho)
        if controle is None or not controle.conectado:
            raise OSError("open failed")
        self._controle = controle

    def set_nonblocking(self, valor):
        pass

    def write(self, dados):
        return self._controle.receber(dados)

    def read(self, tamanho):
        # sem bloqueio: alterna "tem um relatório" e "fila vazia", para o app esvaziar e seguir
        if self._entradas_por_leitura <= 0:
            self._entradas_por_leitura = 1
            return []
        rep = self._controle.relatorio_de_entrada()
        if not rep:
            return []
        self._entradas_por_leitura -= 1
        return rep[:tamanho]

    def error(self):
        return "dispositivo desconectado"

    def close(self):
        self._controle = None


class HidFalso:
    """Substituto do módulo `hid`: enumerate() e device(), com os controles "plugados" nele."""

    def __init__(self):
        self.controles = []

    def plugar(self, controle):
        self.controles.append(controle)
        return controle

    def por_caminho(self, caminho):
        return next((c for c in self.controles if c.caminho == caminho), None)

    def enumerate(self, vendor_id=0, product_id=0):
        return [c.info() for c in self.controles
                if c.conectado and (not vendor_id or vendor_id == SONY)
                and (not product_id or product_id == c.pid)]

    def device(self):
        return _Dispositivo(self)

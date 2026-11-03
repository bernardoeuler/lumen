"""Acesso de baixo nível ao DualShock 4 via HID: achar, abrir e mandar o relatório de saída."""
import zlib

import hid

SONY_VID = 0x054C
DS4_PIDS = (0x05C4, 0x09CC)  # DS4 v1 e v2

# relatório de saída 0x11 (Bluetooth) tem 78 bytes, os 4 últimos são CRC32
BT_REPORT_LEN = 78
# relatório de saída 0x05 (USB) tem 32 bytes, sem CRC
USB_REPORT_LEN = 32

FLAG_RUMBLE = 0x01
FLAG_LIGHT = 0x02
FLAG_FLASH = 0x04
# o clone ignora a luz se a flag de vibração não vier junto (ver testar_luz.py),
# então todo relatório leva todas as flags com o estado completo
FLAGS_TUDO = FLAG_RUMBLE | FLAG_LIGHT | FLAG_FLASH


class ControleNaoEncontrado(Exception):
    pass


def find_controller():
    for d in hid.enumerate(SONY_VID):
        if d["product_id"] in DS4_PIDS:
            return d
    return None


def is_bluetooth(info):
    # no Windows o caminho de um dispositivo Bluetooth contém o GUID do perfil HID (00001124-...)
    path = info["path"].decode(errors="ignore").lower()
    return "00001124" in path or info.get("bus_type") == 2


class DS4:
    def __init__(self):
        info = find_controller()
        if info is None:
            raise ControleNaoEncontrado("Controle DS4 não encontrado. Ele está conectado?")
        self.info = info
        self.bluetooth = is_bluetooth(info)
        self.dev = hid.device()
        try:
            self.dev.open_path(info["path"])
        except OSError as e:
            raise ControleNaoEncontrado(f"Não consegui abrir o controle ({e}).") from e

    def send(self, rgb=(0, 0, 0), forte=0, fraco=0, flags=FLAGS_TUDO):
        r, g, b = rgb
        if self.bluetooth:
            rep = bytearray(BT_REPORT_LEN)
            rep[0] = 0x11
            rep[1] = 0xC0  # habilita HID + CRC
            rep[2] = 0x00
            rep[3] = flags
            base = 6
        else:
            rep = bytearray(USB_REPORT_LEN)
            rep[0] = 0x05
            rep[1] = flags
            base = 4
        rep[base] = fraco      # motor direito (leve)
        rep[base + 1] = forte  # motor esquerdo (pesado)
        rep[base + 2:base + 5] = bytes((r, g, b))
        # bytes base+5 e base+6 seriam o pisca por hardware, que o clone ignora
        if self.bluetooth:
            crc = zlib.crc32(b"\xa2" + rep[:-4])
            rep[-4:] = crc.to_bytes(4, "little")
        written = self.dev.write(bytes(rep))
        if written < 0:
            raise OSError(f"Falha ao enviar: {self.dev.error()}")

    def close(self):
        self.dev.close()

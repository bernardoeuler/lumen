"""Testa variações do relatório de luz para descobrir qual o controle aceita.

Uso: python testar_luz.py   (com Steam, DS4Windows e o app.py fechados)
"""
import zlib

from controle import DS4, BT_REPORT_LEN, ControleNaoEncontrado

# (descrição, byte1, byte2, flags, byte4)
VARIANTES = [
    ("padrão (Linux hid-playstation)", 0xC0, 0x00, 0x02, 0x00),
    ("padrão atual do ds4.py", 0xC0, 0x20, 0x06, 0x00),
    ("todas as flags", 0xC0, 0x00, 0x07, 0x00),
    ("estilo DS4Windows", 0xC4, 0xA0, 0xF7, 0x04),
    ("flags 0xFF", 0xC0, 0x00, 0xFF, 0x00),
    ("byte1 0x80", 0x80, 0x00, 0xFF, 0x00),
]

# uma cor diferente por variante: se a variante falhar, a cor da anterior continua
# acesa, então só conta como sucesso quando aparece exatamente a cor pedida
CORES_TESTE = [
    ("VERMELHO", (255, 0, 0)),
    ("VERDE", (0, 255, 0)),
    ("AZUL", (0, 0, 255)),
    ("AMARELO", (255, 200, 0)),
    ("ROXO", (150, 0, 255)),
    ("CIANO", (0, 255, 255)),
]


def enviar(ds4, b1, b2, flags, b4, rgb):
    rep = bytearray(BT_REPORT_LEN)
    rep[0], rep[1], rep[2], rep[3], rep[4] = 0x11, b1, b2, flags, b4
    rep[8:11] = bytes(rgb)
    crc = zlib.crc32(b"\xa2" + rep[:-4])
    rep[-4:] = crc.to_bytes(4, "little")
    return ds4.dev.write(bytes(rep))


def main():
    try:
        ds4 = DS4()
    except ControleNaoEncontrado as e:
        print(e)
        return
    if not ds4.bluetooth:
        print("Controle está no USB: este teste é só para Bluetooth.")
        print("Teste direto: python ds4.py luz vermelho")
        return
    funcionaram = []
    try:
        for n, ((desc, b1, b2, flags, b4), (nome, rgb)) in enumerate(zip(VARIANTES, CORES_TESTE), 1):
            escritos = enviar(ds4, b1, b2, flags, b4, rgb)
            resp = input(f"[{n}/{len(VARIANTES)}] {desc} (enviado {escritos} bytes). "
                         f"A luz ficou {nome}? (s/n) ").strip().lower()
            if resp.startswith("s"):
                funcionaram.append(n)
    finally:
        ds4.close()
    print()
    print("Variantes que funcionaram:", funcionaram or "nenhuma")


if __name__ == "__main__":
    main()

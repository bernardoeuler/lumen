"""Testa jeitos de apagar a luz: no clone, cor (0, 0, 0) deixa a luz BRANCA em vez de apagar.

Antes de cada variante a luz é posta em AZUL (formato que já funciona), para dar para ver a mudança.
Uso: python testar_apagar.py   (com Steam, DS4Windows e o app.py fechados)
"""
import time
import zlib

from controle import DS4, BT_REPORT_LEN, ControleNaoEncontrado

AZUL = (0, 0, 255)

# (descrição, flags, rgb, pisca_aceso, pisca_apagado)
VARIANTES = [
    ("cor (0,0,0), como o app faz hoje", 0x07, (0, 0, 0), 0, 0),
    ("cor (1,1,1), quase preto", 0x07, (1, 1, 1), 0, 0),
    ("cor (0,0,1)", 0x07, (0, 0, 1), 0, 0),
    ("cor (1,0,0)", 0x07, (1, 0, 0), 0, 0),
    ("pisca de hardware sempre apagado", 0x07, (0, 0, 255), 0, 255),
    ("sem a flag de luz (0x05)", 0x05, (0, 0, 0), 0, 0),
    ("só a flag de luz (0x02)", 0x02, (0, 0, 0), 0, 0),
]


def enviar(ds4, flags, rgb, aceso=0, apagado=0):
    rep = bytearray(BT_REPORT_LEN)
    rep[0], rep[1], rep[2], rep[3] = 0x11, 0xC0, 0x00, flags
    rep[8:11] = bytes(rgb)
    rep[11], rep[12] = aceso, apagado
    crc = zlib.crc32(b"\xa2" + rep[:-4])
    rep[-4:] = crc.to_bytes(4, "little")
    ds4.dev.write(bytes(rep))


def main():
    try:
        ds4 = DS4()
    except ControleNaoEncontrado as e:
        print(e)
        return
    if not ds4.bluetooth:
        print("Controle está no USB: este teste é só para Bluetooth.")
        return
    resultados = []
    try:
        for n, (desc, flags, rgb, aceso, apagado) in enumerate(VARIANTES, 1):
            enviar(ds4, 0x07, AZUL)
            time.sleep(1)
            enviar(ds4, flags, rgb, aceso, apagado)
            resp = input(f"[{n}/{len(VARIANTES)}] {desc}: a luz APAGOU totalmente? "
                         "(s = apagou / b = ficou branca / n = outra coisa) ").strip().lower()[:1]
            resultados.append((n, desc, {"s": "APAGOU", "b": "branca"}.get(resp, "outra")))
    finally:
        enviar(ds4, 0x07, AZUL)
        ds4.close()
    print()
    for n, desc, r in resultados:
        print(f"  {n}. {r:7} {desc}")


if __name__ == "__main__":
    main()

"""Lê os relatórios de entrada do controle por alguns segundos e mostra o byte de status/bateria.

No DS4 original o status fica no byte 30 do relatório USB (0x01) e no byte 32 do Bluetooth (0x11):
nível nos 4 bits de baixo (0..10, até 11 carregando) e o bit 0x10 indica cabo conectado.
Pode rodar com o app aberto (o Windows deixa dois programas lerem o mesmo controle).
"""
import time
from collections import Counter

from controle import find_controller, hid

info = find_controller()
if info is None:
    raise SystemExit("controle não encontrado")
dev = hid.device()
dev.open_path(info["path"])
dev.set_nonblocking(True)

tipos = Counter()
status = Counter()
fim = time.monotonic() + 3
exemplo = None
while time.monotonic() < fim:
    rep = dev.read(128)
    if not rep:
        time.sleep(0.005)
        continue
    tipos[(rep[0], len(rep))] += 1
    pos = {0x11: 32, 0x01: 30}.get(rep[0])
    if pos is not None and len(rep) > pos:
        status[rep[pos]] += 1
        exemplo = rep
dev.close()

print("relatórios (id, tamanho):", dict(tipos))
for valor, n in status.most_common(5):
    print(f"status 0x{valor:02X}: nível {valor & 0x0F}, cabo {bool(valor & 0x10)} ({n}x)")
if exemplo:
    print("exemplo:", " ".join(f"{b:02X}" for b in exemplo[:40]))

"""Dono do controle: guarda o estado completo (cor, pisca, vibração) e o envia numa thread própria.

A GUI só chama os métodos públicos; nunca abre o HID diretamente.
"""
import logging
import threading
import time

from controle import DS4, ControleNaoEncontrado

TICK = 0.01        # resolução do pisca e da vibração
KEEPALIVE = 1.0    # reenvia o estado mesmo sem mudança, caso o controle tenha reconectado
APAGADO = (0, 0, 0)

log = logging.getLogger(__name__)


class Estado:
    def __init__(self):
        self.rgb = APAGADO
        self.pisca = None       # (aceso, apagado, inicio)
        self.forte = 0
        self.fraco = 0
        self.vibra_ate = 0.0

    def saida(self, agora):
        """O que o controle deve mostrar neste instante: (rgb, forte, fraco)."""
        rgb = self.rgb
        if self.pisca:
            aceso, apagado, inicio = self.pisca
            if (agora - inicio) % (aceso + apagado) >= aceso:
                rgb = APAGADO
        if agora < self.vibra_ate:
            return rgb, self.forte, self.fraco
        return rgb, 0, 0


class Gerenciador:
    def __init__(self, ao_mudar_conexao=None):
        """ao_mudar_conexao(conectado, bluetooth) é chamado da thread do controle."""
        self._estado = Estado()
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="controle", daemon=True)
        self._ao_mudar_conexao = ao_mudar_conexao or (lambda conectado, bluetooth: None)

    def iniciar(self):
        self._thread.start()

    def encerrar(self):
        """Para os motores e mantém a cor da luz (o controle guarda sozinho)."""
        with self._trava:
            self._estado.pisca = None
            self._estado.vibra_ate = 0.0
        self._parar.set()
        self._thread.join(timeout=2)

    def luz(self, rgb):
        with self._trava:
            self._estado.rgb = tuple(rgb)

    def piscar(self, aceso, apagado):
        """Pisca na cor atual até parar_pisca()."""
        with self._trava:
            self._estado.pisca = (aceso, apagado, time.monotonic())

    def parar_pisca(self):
        with self._trava:
            self._estado.pisca = None

    def vibrar(self, forte, fraco, segundos):
        with self._trava:
            self._estado.forte = forte
            self._estado.fraco = fraco
            self._estado.vibra_ate = time.monotonic() + segundos

    def parar_vibracao(self):
        with self._trava:
            self._estado.vibra_ate = 0.0

    def _loop(self):
        ds4 = None
        ultimo = None
        ultimo_envio = 0.0
        while not self._parar.is_set():
            if ds4 is None:
                try:
                    ds4 = DS4()
                except ControleNaoEncontrado:
                    self._parar.wait(1)  # tenta de novo até o controle aparecer
                    continue
                ultimo = None
                log.info("controle conectado (%s)", "Bluetooth" if ds4.bluetooth else "USB")
                self._ao_mudar_conexao(True, ds4.bluetooth)

            agora = time.monotonic()
            with self._trava:
                atual = self._estado.saida(agora)
            if atual != ultimo or agora - ultimo_envio >= KEEPALIVE:
                try:
                    ds4.send(*atual)
                except (OSError, ValueError) as e:
                    log.warning("controle desconectado (%s)", e)
                    ds4.close()
                    ds4 = None
                    self._ao_mudar_conexao(False, None)
                    continue
                ultimo = atual
                ultimo_envio = agora
            self._parar.wait(TICK)

        if ds4 is not None:
            with self._trava:
                rgb = self._estado.rgb
            try:
                ds4.send(rgb)  # motores parados, cor mantida
            except (OSError, ValueError):
                pass
            ds4.close()

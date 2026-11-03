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
        self.passos = []           # sequência do pisca: [(rgb, segundos), ...]; APAGADO = pausa
        self.pisca_inicio = None   # None = sem pisca (luz fixa em rgb)
        self.forte = 0
        self.fraco = 0
        self.vibra_ate = 0.0

    def cor_da_sequencia(self, agora):
        total = sum(seg for _, seg in self.passos)
        if total <= 0:
            return self.rgb
        t = (agora - self.pisca_inicio) % total
        for cor, seg in self.passos:
            if t < seg:
                return cor
            t -= seg
        return self.passos[-1][0]  # arredondamento no fim do ciclo

    def saida(self, agora):
        """O que o controle deve mostrar neste instante: (rgb, forte, fraco)."""
        rgb = self.rgb
        if self.pisca_inicio is not None and self.passos:
            rgb = self.cor_da_sequencia(agora)
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
            self._estado.pisca_inicio = None
            self._estado.vibra_ate = 0.0
        self._parar.set()
        self._thread.join(timeout=2)

    def luz(self, rgb):
        with self._trava:
            self._estado.rgb = tuple(rgb)

    def sequencia(self, passos):
        """Define a sequência do pisca: [(rgb, segundos), ...]. Não reinicia o ciclo em andamento."""
        with self._trava:
            self._estado.passos = [(tuple(rgb), float(seg)) for rgb, seg in passos]

    def piscar(self):
        """Começa a percorrer a sequência em ciclo, até parar_pisca(). Se já está piscando, não faz nada."""
        with self._trava:
            if self._estado.pisca_inicio is None:
                self._estado.pisca_inicio = time.monotonic()

    def parar_pisca(self):
        with self._trava:
            self._estado.pisca_inicio = None

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

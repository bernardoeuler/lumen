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


def _indice(duracoes, t):
    """Índice do passo em que o instante t (0 <= t < soma das durações) cai."""
    for i, seg in enumerate(duracoes):
        if t < seg:
            return i
        t -= seg
    return len(duracoes) - 1  # arredondamento no fim do ciclo


class Estado:
    def __init__(self):
        self.rgb = APAGADO
        self.passos = []           # sequência do pisca: [(rgb, segundos), ...]; APAGADO = pausa
        self.pisca_inicio = None   # None = sem pisca (luz fixa em rgb)
        self.forte = 0
        self.fraco = 0
        self.vibra_ate = 0.0
        self.padrao = []           # padrão de vibração: [(forte, fraco, segundos), ...]
        self.padrao_inicio = None  # None = padrão parado
        self.padrao_repetir = False

    def passo_do_padrao(self, agora):
        """Índice do passo do padrão neste instante, ou None se ele está parado ou acabou."""
        if self.padrao_inicio is None:
            return None
        duracoes = [seg for _, _, seg in self.padrao]
        total = sum(duracoes)
        t = agora - self.padrao_inicio
        if total <= 0 or (t >= total and not self.padrao_repetir):
            return None
        return _indice(duracoes, t % total)

    def motores_do_padrao(self, agora):
        """(forte, fraco) do padrão neste instante, ou None se ele acabou."""
        i = self.passo_do_padrao(agora)
        if i is None:
            self.padrao_inicio = None
            return None
        return self.padrao[i][:2]

    def passo_da_sequencia(self, agora):
        """Índice do passo do pisca neste instante, ou None sem pisca."""
        duracoes = [seg for _, seg in self.passos]
        if self.pisca_inicio is None or sum(duracoes) <= 0:
            return None
        return _indice(duracoes, (agora - self.pisca_inicio) % sum(duracoes))

    def cor_da_sequencia(self, agora):
        i = self.passo_da_sequencia(agora)
        return self.rgb if i is None else self.passos[i][0]

    def saida(self, agora):
        """O que o controle deve mostrar neste instante: (rgb, forte, fraco)."""
        rgb = self.rgb
        if self.pisca_inicio is not None and self.passos:
            rgb = self.cor_da_sequencia(agora)
        if self.padrao_inicio is not None:
            motores = self.motores_do_padrao(agora)
            if motores:
                return (rgb, *motores)
        if agora < self.vibra_ate:
            return rgb, self.forte, self.fraco
        return rgb, 0, 0


class Gerenciador:
    def __init__(self, ao_mudar_conexao=None, ao_mudar_bateria=None):
        """ao_mudar_conexao(conectado, bluetooth) e ao_mudar_bateria(porcentagem, no_cabo) são
        chamados da thread do controle; a bateria vem como (None, False) ao desconectar."""
        self._ao_mudar_bateria = ao_mudar_bateria or (lambda porcentagem, no_cabo: None)
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
            self._estado.padrao_inicio = None
        self._parar.set()
        if self._thread.is_alive():  # no --smoke-test a thread nem chega a começar
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
            self._estado.padrao_inicio = None
            self._estado.forte = forte
            self._estado.fraco = fraco
            self._estado.vibra_ate = time.monotonic() + segundos

    def padrao_vibracao(self, passos):
        """Define o padrão: [(forte, fraco, segundos), ...]. Não reinicia um padrão em andamento."""
        with self._trava:
            self._estado.padrao = [(int(f), int(r), float(s)) for f, r, s in passos]

    def tocar_padrao(self, repetir, com_pisca=False):
        """Toca o padrão do início; uma vez, ou em ciclo até parar_vibracao() se repetir.

        com_pisca: se o pisca está ligado, ele também volta ao primeiro passo, no mesmo instante
        (os dois começam juntos e depois cada um segue o próprio ciclo).
        """
        with self._trava:
            agora = time.monotonic()
            self._estado.vibra_ate = 0.0
            self._estado.padrao_repetir = repetir
            self._estado.padrao_inicio = agora
            if com_pisca and self._estado.pisca_inicio is not None:
                self._estado.pisca_inicio = agora

    def repetir_padrao(self, repetir):
        with self._trava:
            self._estado.padrao_repetir = repetir

    def parar_vibracao(self):
        with self._trava:
            self._estado.vibra_ate = 0.0
            self._estado.padrao_inicio = None

    def andamento(self):
        """(passo do pisca, passo do padrão, vibração simples ativa) agora, para a GUI mostrar."""
        agora = time.monotonic()
        with self._trava:
            e = self._estado
            return e.passo_da_sequencia(agora), e.passo_do_padrao(agora), agora < e.vibra_ate

    def _loop(self):
        ds4 = None
        ultimo = None
        ultimo_envio = 0.0
        bateria = None
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
                    if bateria is not None:
                        bateria = None
                        self._ao_mudar_bateria(None, False)
                    continue
                ultimo = atual
                ultimo_envio = agora
            try:
                lida = ds4.ler_bateria()
            except (OSError, ValueError):
                lida = None  # a desconexão é tratada no próximo envio
            if lida is not None and lida != bateria:
                bateria = lida
                log.info("bateria %d%%%s", lida[0], " (no cabo)" if lida[1] else "")
                self._ao_mudar_bateria(*lida)
            self._parar.wait(TICK)

        if ds4 is not None:
            with self._trava:
                rgb = self._estado.rgb
            try:
                ds4.send(rgb)  # motores parados, cor mantida
            except (OSError, ValueError):
                pass
            ds4.close()

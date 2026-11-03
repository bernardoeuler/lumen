r"""Lumen: programa com GUI (wxPython) que é o dono do controle DS4: luz, pisca e vibração.

Fechar a janela minimiza para a bandeja; o programa só encerra pelo "Sair" no ícone da bandeja.
Abrir o programa de novo só traz a janela da instância que já está rodando.

Uso (desenvolvimento): .\.venv\Scripts\pythonw.exe app.py
"""
import ctypes
import logging
import math
import os
import sys
import traceback

import wx
import wx.adv

import config
import instancia
import preset
import versao
from gerenciador import Gerenciador

TITULO = "Lumen"

PRESETS = [
    ("Vermelho", (255, 0, 0)),
    ("Laranja", (255, 80, 0)),
    ("Amarelo", (255, 200, 0)),
    ("Verde", (0, 255, 0)),
    ("Ciano", (0, 255, 255)),
    ("Azul", (0, 0, 255)),
    ("Roxo", (150, 0, 255)),
    ("Rosa", (255, 0, 120)),
    ("Branco", (255, 255, 255)),
]
APAGADO = (0, 0, 0)
COR_CONECTADO = wx.Colour(46, 160, 67)
COR_DESCONECTADO = wx.Colour(160, 160, 160)


def criar_icone(rgb, tamanho=32):
    icone = wx.Icon()
    icone.CopyFromBitmap(wx.Bitmap(criar_imagem(rgb, tamanho)))
    return icone


def criar_imagem(rgb, tamanho=32):
    """Círculo na cor da luz (contorno cinza quando apagada), com bordas suavizadas."""
    img = wx.Image(tamanho, tamanho)
    img.InitAlpha()
    centro = (tamanho - 1) / 2
    raio = tamanho / 2 - 1
    apagada = tuple(rgb) == APAGADO
    for y in range(tamanho):
        for x in range(tamanho):
            d = math.hypot(x - centro, y - centro)
            cobertura = max(0.0, min(1.0, raio - d + 0.5))
            if apagada:
                # só um anel
                cobertura *= max(0.0, min(1.0, d - (raio - 3) + 0.5))
                cor = (128, 128, 128)
            else:
                cor = rgb
            img.SetRGB(x, y, *cor)
            img.SetAlpha(x, y, int(cobertura * 255))
    return img


def com_brilho(rgb, brilho):
    return tuple(round(c * brilho / 100) for c in rgb)


def tom_apagado(rgb):
    """O "apagado" possível no clone: a cor no menor brilho (cada canal aceso vira 1).

    O clone mostra branco com (0, 0, 0) e não tem comando para apagar de vez; usar o tom mais
    escuro da cor em uso faz o "apagado" combinar com ela, em vez de ser sempre o mesmo tom.
    Devolve APAGADO para APAGADO (o controle.py então usa o tom padrão).
    """
    return tuple(1 if c else 0 for c in rgb)


def sequencia_para_envio(passos, ligada, cor_base):
    """Passos [r, g, b, s] como serão enviados: pausas viram o tom apagado da cor anterior."""
    cores = [tuple(p[:3]) for p in passos]
    acesas = [c for c in cores if c != APAGADO]
    saida = []
    for i, (cor, p) in enumerate(zip(cores, passos)):
        if not ligada:
            cor = tom_apagado(cor_base)
        elif cor == APAGADO:
            # cor acesa mais próxima antes desta (em ciclo); sem nenhuma, a cor da luz
            anteriores = [c for c in cores[:i][::-1] + cores[i:][::-1] if c != APAGADO]
            cor = tom_apagado(anteriores[0] if acesas else cor_base)
        saida.append((cor, p[3]))
    return saida


def largura_campo(janela, dip):
    """Tamanho de um campo numérico: largura fixa no Windows; no GTK o campo leva os botões +/- ao
    lado e precisa do tamanho natural (senão corta o número)."""
    return wx.Size(janela.FromDIP(dip) if sys.platform == "win32" else -1, -1)


def segundos(s):
    """Duração curta para o rótulo de um passo: 0.5 -> '0,5 s'."""
    return f"{round(s, 2):g} s".replace(".", ",")


def contorno(rgb):
    """Cor de borda que aparece tanto em cores claras quanto escuras."""
    return wx.Colour(*(int(c * 0.6) for c in rgb)) if sum(rgb) > 300 else wx.Colour(0, 0, 0, 60)


class Bolinha(wx.Control):
    """Botão redondo de cor, com anel quando selecionado."""

    def __init__(self, pai, rgb, nome, ao_clicar):
        tam = pai.FromDIP(wx.Size(30, 30))
        super().__init__(pai, size=tam, style=wx.BORDER_NONE)
        self.rgb = rgb
        self.selecionada = False
        self.sobre = False
        self.SetToolTip(nome)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_UP, lambda e: ao_clicar(self.rgb))
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self._sobre(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self._sobre(False))

    def DoGetBestSize(self):
        return self.FromDIP(wx.Size(30, 30))

    def _sobre(self, valor):
        self.sobre = valor
        self.Refresh()

    def selecionar(self, valor):
        if valor != self.selecionada:
            self.selecionada = valor
            self.Refresh()

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        d = min(w, h)
        anel = self.FromDIP(2)
        folga = self.FromDIP(4)
        if self.selecionada or self.sobre:
            cor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
            if not self.selecionada:
                cor = wx.Colour(cor.Red(), cor.Green(), cor.Blue(), 110)
            gc.SetPen(wx.Pen(cor, anel))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.DrawEllipse(anel / 2, anel / 2, d - anel, d - anel)
        if self.rgb == APAGADO:
            # pausa da sequência: disco escuro com borda cinza
            gc.SetPen(wx.Pen(wx.Colour(120, 120, 120), 1))
            gc.SetBrush(wx.Brush(wx.Colour(40, 40, 40)))
        else:
            gc.SetPen(wx.Pen(contorno(self.rgb), 1))
            gc.SetBrush(wx.Brush(wx.Colour(*self.rgb)))
        gc.DrawEllipse(folga, folga, d - 2 * folga, d - 2 * folga)


class Indicador(wx.Control):
    """Bolinha de status (verde = conectado)."""

    def __init__(self, pai):
        super().__init__(pai, size=pai.FromDIP(wx.Size(12, 12)), style=wx.BORDER_NONE)
        self.cor = COR_DESCONECTADO
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def DoGetBestSize(self):
        return self.FromDIP(wx.Size(12, 12))

    def definir(self, cor):
        self.cor = cor
        self.Refresh()

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(self.cor))
        gc.DrawEllipse(1, 1, w - 2, h - 2)


class Bateria(wx.Control):
    """Pilha minimalista: contorno fino, preenchimento na cor do nível, raio no cabo, % ao lado."""

    def __init__(self, pai):
        # no GTK a cor informada pelo pai difere do fundo do tema, e pintá-la deixaria um retângulo;
        # o fundo transparente precisa ser definido antes de criar a janela
        super().__init__()
        self.transparente = sys.platform != "win32" and pai.IsTransparentBackgroundSupported()
        self.SetBackgroundStyle(wx.BG_STYLE_TRANSPARENT if self.transparente else wx.BG_STYLE_PAINT)
        self.Create(pai, style=wx.BORDER_NONE)
        self.porcentagem = None  # None = sem leitura (desconectado)
        self.no_cabo = False
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def DoGetBestSize(self):
        # mede o maior texto com a fonte real: a do GTK é maior que a do Windows
        tw, th = self.GetTextExtent("100%")
        return wx.Size(tw + self.FromDIP(5 + 22 + 2 + 4), max(th, self.FromDIP(16)))

    def definir(self, porcentagem, no_cabo):
        self.porcentagem, self.no_cabo = porcentagem, no_cabo
        # sem leitura some de vez (no GTK, um controle vazio aparece como um retângulo de outra cor)
        if self.IsShown() != (porcentagem is not None):
            self.Show(porcentagem is not None)
            self.GetParent().Layout()
        self.SetToolTip(None if porcentagem is None else
                        f"Bateria {porcentagem}%" + (" (carregando)" if no_cabo else ""))
        self.Refresh()

    def on_paint(self, _):
        if self.transparente:
            self.desenhar(wx.PaintDC(self))
            return
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        self.desenhar(dc)

    def desenhar(self, dc):
        if self.porcentagem is None:
            return
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        cinza = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        p = self.porcentagem

        # texto à esquerda, pilha encostada à direita
        gc.SetFont(self.GetFont(), cinza)
        texto = f"{p}%"
        tw, th = gc.GetTextExtent(texto)
        corpo_w, corpo_h = self.FromDIP(22), self.FromDIP(11)
        bico_w = self.FromDIP(2)
        x = w - corpo_w - bico_w - 1
        y = (h - corpo_h) / 2
        gc.DrawText(texto, x - self.FromDIP(5) - tw, (h - th) / 2)

        gc.SetPen(wx.Pen(cinza, self.FromDIP(1)))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(x, y, corpo_w, corpo_h, self.FromDIP(3))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(cinza))
        gc.DrawRoundedRectangle(x + corpo_w, y + corpo_h * 0.3, bico_w, corpo_h * 0.4, 1)

        if p > 30 or self.no_cabo:
            cor = COR_CONECTADO
        elif p > 10:
            cor = wx.Colour(230, 160, 0)
        else:
            cor = wx.Colour(215, 50, 50)
        folga = self.FromDIP(2)
        cheio = (corpo_w - 2 * folga) * max(p, 5) / 100  # vazio ainda mostra um tiquinho
        gc.SetBrush(wx.Brush(cor))
        gc.DrawRoundedRectangle(x + folga, y + folga, cheio, corpo_h - 2 * folga, self.GetDPIScaleFactor() * 1.5)

        if self.no_cabo:
            # raio no meio da pilha, com borda na cor do fundo para destacar do preenchimento
            cx, cy, a = x + corpo_w / 2, y + corpo_h / 2, corpo_h * 0.42
            raio = gc.CreatePath()
            raio.MoveToPoint(cx + a * 0.25, cy - a)
            raio.AddLineToPoint(cx - a * 0.45, cy + a * 0.12)
            raio.AddLineToPoint(cx - a * 0.02, cy + a * 0.12)
            raio.AddLineToPoint(cx - a * 0.25, cy + a)
            raio.AddLineToPoint(cx + a * 0.45, cy - a * 0.12)
            raio.AddLineToPoint(cx + a * 0.02, cy - a * 0.12)
            raio.CloseSubpath()
            sobre_cor = x + folga + cheio >= cx  # o preenchimento chega ao meio?
            gc.SetPen(wx.Pen(cor if sobre_cor else self.GetParent().GetBackgroundColour(), self.FromDIP(1)))
            gc.SetBrush(wx.Brush(wx.WHITE if sobre_cor else cinza))
            gc.DrawPath(raio)


class BotaoMenu(wx.Control):
    """Botão discreto de 'mais opções' (três pontinhos), sem borda: cinza parado, fundo suave e cor
    de destaque sob o mouse. ao_clicar(botao) normalmente abre um menu logo abaixo dele."""

    def __init__(self, pai, dica, ao_clicar):
        super().__init__(pai, style=wx.BORDER_NONE)
        self.sobre = False
        self.SetToolTip(dica)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_UP, lambda e: ao_clicar(self))
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self._sobre(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self._sobre(False))

    def DoGetBestSize(self):
        return self.FromDIP(wx.Size(26, 26))

    def _sobre(self, valor):
        self.sobre = valor
        self.Refresh()

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        destaque = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        if self.sobre:
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(wx.Brush(wx.Colour(destaque.Red(), destaque.Green(), destaque.Blue(), 40)))
            gc.DrawRoundedRectangle(0, 0, w, h, self.FromDIP(6))
        cor = destaque if self.sobre else wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        # três pontinhos na horizontal
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(cor))
        r, vao = 1.6 * self.GetDPIScaleFactor(), self.FromDIP(5)
        for k in (-1, 0, 1):
            gc.DrawEllipse(w / 2 + k * vao - r, h / 2 - r, 2 * r, 2 * r)


class Previa(wx.Control):
    """Retângulo arredondado com a cor que está indo para o controle."""

    def __init__(self, pai):
        super().__init__(pai, size=pai.FromDIP(wx.Size(64, 64)), style=wx.BORDER_NONE)
        self.rgb = APAGADO
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def DoGetBestSize(self):
        return self.FromDIP(wx.Size(64, 64))

    def definir(self, rgb):
        self.rgb = rgb
        self.Refresh()

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        raio = self.FromDIP(10)
        apagada = self.rgb == APAGADO
        gc.SetPen(wx.Pen(wx.Colour(120, 120, 120) if apagada else contorno(self.rgb), 1))
        gc.SetBrush(wx.Brush(wx.Colour(40, 40, 40) if apagada else wx.Colour(*self.rgb)))
        gc.DrawRoundedRectangle(0.5, 0.5, w - 1, h - 1, raio)
        if apagada:
            gc.SetFont(self.GetFont(), wx.Colour(170, 170, 170))
            tw, th = gc.GetTextExtent("off")
            gc.DrawText("off", (w - tw) / 2, (h - th) / 2)


def desenhar_bolinha(gc, x, y, d, rgb, alfa=255):
    """Bolinha de cor (ou pausa apagada) no retângulo (x, y, d, d)."""
    if tuple(rgb) == APAGADO:
        gc.SetPen(wx.Pen(wx.Colour(120, 120, 120, alfa), 1))
        gc.SetBrush(wx.Brush(wx.Colour(40, 40, 40, alfa)))
    else:
        borda = contorno(rgb)
        gc.SetPen(wx.Pen(wx.Colour(borda.Red(), borda.Green(), borda.Blue(), min(borda.Alpha(), alfa)), 1))
        gc.SetBrush(wx.Brush(wx.Colour(*rgb, alfa)))
    gc.DrawEllipse(x, y, d, d)


def desenhar_vibracao(gc, x, y, d, forte, fraco, alfa=255):
    """Bolinha neutra com duas barras: esquerda = motor forte, direita = motor fraco (0..255)."""
    fundo = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
    borda = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW)
    gc.SetPen(wx.Pen(wx.Colour(borda.Red(), borda.Green(), borda.Blue(), alfa), 1))
    gc.SetBrush(wx.Brush(wx.Colour(fundo.Red(), fundo.Green(), fundo.Blue(), alfa)))
    gc.DrawEllipse(x, y, d, d)
    barra = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.SetBrush(wx.Brush(wx.Colour(barra.Red(), barra.Green(), barra.Blue(), alfa)))
    largura, vao = d * 0.2, d * 0.1
    base, altura_max = y + d * 0.8, d * 0.6
    for i, valor in enumerate((forte, fraco)):
        bx = x + d / 2 - vao / 2 - largura + i * (largura + vao)
        h = max(1.0, altura_max * valor / 255)  # parado aparece como um traço
        gc.DrawRoundedRectangle(bx, base - h, largura, h, min(largura / 2, h / 2))


class Miniatura(wx.Control):
    """Desenho fixo de um item (usado no topo do balão de detalhe)."""

    def __init__(self, pai, desenhar):
        super().__init__(pai, size=pai.FromDIP(wx.Size(30, 30)), style=wx.BORDER_NONE)
        self.desenhar = desenhar  # (gc, x, y, d)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def DoGetBestSize(self):
        return self.FromDIP(wx.Size(30, 30))

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        folga = self.FromDIP(4)
        d = min(self.GetClientSize()) - 2 * folga
        self.desenhar(gc, folga, folga, d)


class Faixa(wx.Control):
    """Sequência como uma fileira de bolinhas (cores do pisca ou passos da vibração).

    Cada passo mostra a duração embaixo; o passo que está tocando no controle fica destacado.
    Clique numa bolinha abre o detalhe dela; arrastar muda a ordem; a última bolinha ('+') adiciona.
    `itens` é a lista do editor, compartilhada; `desenhar(gc, x, y, d, item, alfa)` desenha um item,
    `dica(item)` dá o texto ao passar o mouse e `rotulo(item)` o texto embaixo dele.
    """

    POR_LINHA = 9
    LIMIAR_ARRASTO = 4  # px que o mouse precisa andar para virar arrasto
    AJUDA = "Clique para editar · arraste para mudar a ordem"

    def __init__(self, pai, itens, desenhar, dica, rotulo, dica_adicionar, ao_clicar, ao_mover, ao_adicionar):
        super().__init__(pai, style=wx.BORDER_NONE)
        self.itens = itens
        self.desenhar = desenhar
        self.dica = dica
        self.rotulo = rotulo
        self.dica_adicionar = dica_adicionar
        self.ao_clicar = ao_clicar        # (indice)
        self.ao_mover = ao_mover          # (origem, posicao_de_insercao)
        self.ao_adicionar = ao_adicionar  # (retangulo_na_tela)
        self.selecionado = None
        self.tocando = None               # passo que está no controle agora
        self.sobre = None
        self.pressionado = None           # índice onde o botão foi apertado
        self.inicio_arrasto = None
        self.arrastando = False
        self.mouse = wx.Point()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_down)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_LEFT_UP, self.on_up)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: self._cancelar())
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self._definir_sobre(None))

    # célula de cada passo: bolinha em cima, duração embaixo
    @property
    def cw(self):
        return max(self.FromDIP(40), self._rotulo_maior()[0] + self.FromDIP(6))

    @property
    def ch(self):
        return self.FromDIP(5) + self.d + self.FromDIP(4) + self._rotulo_maior()[1] + self.FromDIP(3)

    def _rotulo_maior(self):
        """(largura, altura) do maior rótulo de duração, medidos com a fonte real."""
        return self.GetFullTextExtent("10,25 s", self.GetFont().Smaller())[:2]

    @property
    def d(self):
        return self.FromDIP(24)

    def _n(self):
        return len(self.itens) + 1  # + a bolinha de adicionar

    def DoGetBestSize(self):
        linhas = (self._n() + self.POR_LINHA - 1) // self.POR_LINHA
        return wx.Size(self.POR_LINHA * self.cw, linhas * self.ch)

    def atualizar(self):
        self.InvalidateBestSize()
        self.Refresh()

    def tocar(self, i):
        if i != self.tocando:
            self.tocando = i
            self.Refresh()

    def _ret(self, i):
        linha, col = divmod(i, self.POR_LINHA)
        return wx.Rect(col * self.cw, linha * self.ch, self.cw, self.ch)

    def _bolinha(self, i):
        """(x, y) do canto da bolinha do passo i."""
        r = self._ret(i)
        return r.x + (self.cw - self.d) / 2, r.y + self.FromDIP(5)

    def _indice_em(self, pt):
        col, linha = pt.x // self.cw, pt.y // self.ch
        i = linha * self.POR_LINHA + col
        return i if 0 <= col < self.POR_LINHA and 0 <= i < self._n() else None

    def _insercao(self, pt):
        """Posição (0..len) onde o item arrastado entraria se soltasse em pt."""
        linhas = max(1, (len(self.itens) + self.POR_LINHA - 1) // self.POR_LINHA)
        linha = max(0, min(linhas - 1, pt.y // self.ch))
        col = max(0, min(self.POR_LINHA, round(pt.x / self.cw)))
        return max(0, min(len(self.itens), linha * self.POR_LINHA + col))

    def na_tela(self, i):
        r = self._ret(i)
        return wx.Rect(self.ClientToScreen(r.GetTopLeft()), r.GetSize())

    def _definir_sobre(self, i):
        if i != self.sobre:
            self.sobre = i
            if i is not None and i < len(self.itens):
                self.SetToolTip(f"{self.dica(self.itens[i])}\n{self.AJUDA}")
            else:
                self.SetToolTip(self.dica_adicionar if i is not None else None)
            self.Refresh()

    def on_down(self, ev):
        i = self._indice_em(ev.GetPosition())
        if i is None:
            return
        self.pressionado = i
        self.inicio_arrasto = ev.GetPosition()
        if i < len(self.itens):
            self.CaptureMouse()

    def on_motion(self, ev):
        self.mouse = ev.GetPosition()
        if self.pressionado is None or self.pressionado >= len(self.itens) or not ev.LeftIsDown():
            self._definir_sobre(self._indice_em(self.mouse))
            return
        if not self.arrastando:
            dx = abs(self.mouse.x - self.inicio_arrasto.x)
            dy = abs(self.mouse.y - self.inicio_arrasto.y)
            if max(dx, dy) < self.FromDIP(self.LIMIAR_ARRASTO):
                return
            self.arrastando = True
            self.SetToolTip(None)
        self.Refresh()

    def on_up(self, ev):
        i, arrastando = self.pressionado, self.arrastando
        destino = self._insercao(ev.GetPosition()) if arrastando else None
        self._cancelar()
        if i is None:
            return
        if arrastando:
            self.ao_mover(i, destino)
        elif self._indice_em(ev.GetPosition()) == i:
            if i < len(self.itens):
                self.ao_clicar(i)
            else:
                self.ao_adicionar(self.na_tela(i))

    def _cancelar(self):
        if self.HasCapture():
            self.ReleaseMouse()
        self.pressionado = None
        self.arrastando = False
        self.Refresh()

    def on_paint(self, _):
        self.desenhar_em(wx.AutoBufferedPaintDC(self))

    def desenhar_em(self, dc):
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        d = self.d
        anel = self.FromDIP(2)
        folga = self.FromDIP(3)  # entre a bolinha e o anel de seleção
        destaque = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        cinza = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        fonte = self.GetFont().Smaller()

        for i, item in enumerate(self.itens):
            r = self._ret(i)
            x, y = self._bolinha(i)
            if i == self.tocando and not self.arrastando:
                # fundo suave na célula do passo que está no controle agora
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.SetBrush(wx.Brush(wx.Colour(destaque.Red(), destaque.Green(), destaque.Blue(), 45)))
                gc.DrawRoundedRectangle(r.x + 1, r.y + 1, r.width - 2, r.height - 2, self.FromDIP(6))
            if i in (self.selecionado, self.sobre) and not self.arrastando:
                alfa = 255 if i == self.selecionado else 110
                gc.SetPen(wx.Pen(wx.Colour(destaque.Red(), destaque.Green(), destaque.Blue(), alfa), anel))
                gc.SetBrush(wx.TRANSPARENT_BRUSH)
                gc.DrawEllipse(x - folga, y - folga, d + 2 * folga, d + 2 * folga)
            # o item sendo arrastado fica "fantasma" no lugar de origem
            alfa = 70 if self.arrastando and i == self.pressionado else 255
            self.desenhar(gc, x, y, d, item, alfa)
            texto = self.rotulo(item)
            gc.SetFont(fonte, destaque if i == self.tocando else cinza)
            tw, _ = gc.GetTextExtent(texto)
            gc.DrawText(texto, r.x + (r.width - tw) / 2, y + d + self.FromDIP(4))

        # bolinha de adicionar: contorno tracejado com '+'
        x, y = self._bolinha(len(self.itens))
        cor = destaque if self.sobre == len(self.itens) else cinza
        # no GTK, traços de largura ímpar ganham 0,5 px de ajuste e os pares não; sem o ajuste, o círculo
        # e o '+' ficam com o mesmo centro
        gc.DisableOffset()
        gc.SetPen(wx.Pen(cor, self.FromDIP(1), wx.PENSTYLE_SHORT_DASH))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawEllipse(x, y, d, d)
        c, braco = d / 2, d / 4
        gc.SetPen(wx.Pen(cor, self.FromDIP(2)))
        mais = gc.CreatePath()
        mais.MoveToPoint(x + c - braco, y + c)
        mais.AddLineToPoint(x + c + braco, y + c)
        mais.MoveToPoint(x + c, y + c - braco)
        mais.AddLineToPoint(x + c, y + c + braco)
        gc.StrokePath(mais)

        if self.arrastando:
            # barra onde o item vai entrar + o item seguindo o mouse
            pos = self._insercao(self.mouse)
            linha, col = divmod(pos, self.POR_LINHA)
            if col == 0 and pos > 0 and pos == len(self.itens) and pos % self.POR_LINHA == 0:
                linha, col = linha - 1, self.POR_LINHA
            bx, by = col * self.cw, linha * self.ch + self.FromDIP(5)
            gc.SetPen(wx.Pen(destaque, self.FromDIP(3)))
            gc.StrokeLine(bx, by, bx, by + d)
            self.desenhar(gc, self.mouse.x - d / 2, self.mouse.y - d / 2, d, self.itens[self.pressionado], 200)


class DetalhePasso(wx.Frame):
    """Balão com o detalhe de um passo da sequência.

    O topo e os campos vêm do editor (`preencher(balao, painel, raiz, i)`); os botões de ordem,
    duplicar e remover são comuns. É uma janela sem moldura, e não um PopupTransientWindow, porque
    no Windows o popup não recebe o teclado (os campos só mudavam pelas setinhas). Fecha ao perder
    o foco ou com Esc.
    """

    def __init__(self, editor, i):
        super().__init__(editor.janela, style=wx.FRAME_NO_TASKBAR | wx.FRAME_FLOAT_ON_PARENT | wx.BORDER_SIMPLE)
        self.editor = editor
        self.fechado = False
        self.Bind(wx.EVT_ACTIVATE, lambda ev: ev.GetActive() or self.fechar())
        self.Bind(wx.EVT_CHAR_HOOK, lambda ev: self.fechar() if ev.GetKeyCode() == wx.WXK_ESCAPE else ev.Skip())
        e = self.FromDIP(6)

        painel = wx.Panel(self)
        painel.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        raiz = wx.BoxSizer(wx.VERTICAL)
        editor.preencher(self, painel, raiz, i)

        n = len(editor.itens)
        linha = wx.BoxSizer(wx.HORIZONTAL)
        for rotulo, acao, ativo in (
            ("Antes", lambda ev: self.acao(editor.mover, i, -1), i > 0),
            ("Depois", lambda ev: self.acao(editor.mover, i, +1), i < n - 1),
            ("Duplicar", lambda ev: self.acao(editor.duplicar, i), True),
            ("Remover", lambda ev: self.acao(editor.remover, i), True),
        ):
            bt = wx.Button(painel, label=rotulo, style=wx.BU_EXACTFIT)
            bt.Bind(wx.EVT_BUTTON, acao)
            bt.Enable(ativo)
            linha.Add(bt, 0, wx.RIGHT, self.FromDIP(4))
        raiz.Add(linha, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        painel.SetSizer(raiz)
        raiz.Fit(painel)
        self.SetClientSize(painel.GetSize())

    @staticmethod
    def titulo(painel, raiz, miniatura, titulo, subtitulo):
        """Topo padrão: miniatura + título em negrito + subtítulo cinza."""
        e = painel.FromDIP(6)
        topo = wx.BoxSizer(wx.HORIZONTAL)
        topo.Add(miniatura, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        texto = wx.BoxSizer(wx.VERTICAL)
        t = wx.StaticText(painel, label=titulo)
        t.SetFont(t.GetFont().Bold())
        texto.Add(t)
        s = wx.StaticText(painel, label=subtitulo)
        s.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        texto.Add(s)
        topo.Add(texto, 0, wx.ALIGN_CENTER_VERTICAL)
        raiz.Add(topo, 0, wx.ALL, e)

    def acao(self, funcao, *args):
        # fecha o balão antes: a ação pode abrir um diálogo ou remontar a sequência
        self.fechar()
        wx.CallAfter(funcao, *args)

    def Position(self, ponto, folga, altura_item=0):
        """Abre abaixo do item; se não couber na tela, acima dele (como o PopupTransientWindow)."""
        tela = wx.Display(wx.Display.GetFromPoint(ponto)).GetClientArea()
        w, h = self.GetSize()
        x = max(tela.x, min(ponto.x, tela.Right - w))
        y = ponto.y + folga.height
        if y + h > tela.Bottom:
            y = ponto.y - altura_item - folga.height - h
        self.Move(x, max(tela.y, y))

    def Popup(self):
        self.Show()
        self.Raise()

    def fechar(self):
        if self.fechado:
            return
        self.fechado = True
        self.Hide()
        self.editor.detalhe_fechado(self)


class EditorSequencia:
    """Liga uma lista de passos à sua Faixa e ao balão de detalhe (usado pelo pisca e pela vibração).

    itens: lista de passos (listas), alterada no lugar.
    preencher(balao, painel, raiz, i): monta o topo e os campos do detalhe do passo i.
    novos: [(rótulo, fábrica)] do menu do '+'; a fábrica devolve o novo passo ou None (cancelado).
    ao_mudar(): chamado depois de qualquer alteração (aplicar no controle e salvar).
    """

    def __init__(self, janela, pai, itens, desenhar, dica, rotulo, dica_adicionar, preencher, novos, ao_mudar,
                 ao_mudar_ciclo=lambda: None):
        """ao_mudar_ciclo(): chamado depois de adicionar, duplicar ou remover um passo (o ciclo
        muda de tamanho)."""
        self.janela = janela
        self.itens = itens
        self.preencher = preencher
        self.novos = novos
        self.ao_mudar = ao_mudar
        self.ao_mudar_ciclo = ao_mudar_ciclo
        self.detalhe = None
        self.faixa = Faixa(pai, itens, desenhar, dica, rotulo, dica_adicionar,
                           self.abrir_detalhe, self.arrastar, self.menu_adicionar)

    def alterar(self):
        self.faixa.atualizar()
        self.janela.reajustar()  # a faixa ganha outra fileira a cada 9 itens
        self.ao_mudar()

    def mudar_campo(self, i, campo, valor):
        """Muda um campo do passo i (ex.: a duração) sem remontar nada."""
        self.itens[i][campo] = valor
        self.faixa.Refresh()
        self.ao_mudar()

    def abrir_detalhe(self, i):
        if self.detalhe:
            self.detalhe.fechar()
        self.detalhe = DetalhePasso(self, i)
        ret = self.faixa.na_tela(i)
        self.detalhe.Position(ret.GetBottomLeft(), wx.Size(0, self.faixa.FromDIP(2)), ret.height)
        self.faixa.selecionado = i
        self.faixa.Refresh()
        self.detalhe.Popup()

    def reabrir(self, i):
        if 0 <= i < len(self.itens):
            self.abrir_detalhe(i)

    def detalhe_fechado(self, detalhe):
        if detalhe is self.detalhe:
            self.detalhe = None
            self.faixa.selecionado = None
            self.faixa.Refresh()
        wx.CallAfter(detalhe.Destroy)

    def menu_adicionar(self, ret_na_tela):
        menu = wx.Menu()
        for rotulo, fabrica in self.novos:
            item = menu.Append(wx.ID_ANY, rotulo)
            self.janela.Bind(wx.EVT_MENU, lambda ev, f=fabrica: self.adicionar(f()), item)
        self.faixa.PopupMenu(menu, self.faixa.ScreenToClient(ret_na_tela.GetBottomLeft()))
        menu.Destroy()

    def adicionar(self, passo):
        if passo is not None:
            self.itens.append(list(passo))
            self.alterar()
            self.ao_mudar_ciclo()

    def arrastar(self, origem, insercao):
        """Solta o passo `origem` na posição `insercao` (0..len, contada antes de tirá-lo)."""
        destino = insercao - 1 if insercao > origem else insercao
        if destino != origem:
            self.itens.insert(destino, self.itens.pop(origem))
            self.alterar()

    def mover(self, i, delta):
        j = i + delta
        self.itens[i], self.itens[j] = self.itens[j], self.itens[i]
        self.alterar()
        self.reabrir(j)  # o detalhe acompanha o passo na nova posição

    def duplicar(self, i):
        """Insere uma cópia logo depois e abre o detalhe da cópia."""
        self.itens.insert(i + 1, list(self.itens[i]))
        self.alterar()
        self.ao_mudar_ciclo()
        self.reabrir(i + 1)

    def remover(self, i):
        del self.itens[i]
        self.alterar()
        self.ao_mudar_ciclo()


class IconeBandeja(wx.adv.TaskBarIcon):
    def __init__(self, janela):
        super().__init__()
        self.janela = janela
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, lambda e: janela.mostrar())

    def CreatePopupMenu(self):
        menu = wx.Menu()
        self.Bind(wx.EVT_MENU, lambda e: self.janela.mostrar(), menu.Append(wx.ID_ANY, "Mostrar"))
        menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, lambda e: self.janela.sair(), menu.Append(wx.ID_EXIT, "Sair"))
        return menu


class Janela(wx.Frame):
    def __init__(self, gerenciador, cfg):
        super().__init__(None, title=TITULO, style=wx.DEFAULT_FRAME_STYLE & ~(wx.MAXIMIZE_BOX | wx.RESIZE_BORDER))
        self.g = gerenciador
        self.cfg = cfg
        self.cor = tuple(cfg["cor"])       # cor escolhida (100% de brilho)
        self.ligada = True                 # False = "Apagar"
        self.saindo = False
        self.avisou_bandeja = False
        self.bandeja = IconeBandeja(self)
        self._salvar_depois = wx.CallLater(500, self.salvar_config)
        self._salvar_depois.Stop()

        painel = wx.Panel(self)
        self.painel = painel
        m = self.FromDIP(12)   # margem
        e = self.FromDIP(6)    # espaço entre itens
        raiz = wx.BoxSizer(wx.VERTICAL)
        # coluna dos rótulos ("Motor forte", "Piscar"...): cabe o maior texto, com espaço para a caixa
        # de marcar; a fonte do GTK é maior que a do Windows, então não dá para fixar
        rotulos = ("Motor forte", "Motor fraco", "Brilho (%)", "Duração (s)", "Padrão", "Piscar")
        self.col = max(self.FromDIP(78),
                       max(painel.GetTextExtent(t).width for t in rotulos) + self.FromDIP(28))

        # --- cabeçalho: status da conexão
        linha = wx.BoxSizer(wx.HORIZONTAL)
        self.indicador = Indicador(painel)
        linha.Add(self.indicador, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        self.status = wx.StaticText(painel, label="Procurando controle…")
        linha.Add(self.status, 1, wx.ALIGN_CENTER_VERTICAL)
        self.bateria = Bateria(painel)
        self.bateria.Hide()  # aparece na primeira leitura
        linha.Add(self.bateria, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        linha.Add(BotaoMenu(painel, "Mais opções", self.menu_opcoes), 0, wx.ALIGN_CENTER_VERTICAL)
        raiz.Add(linha, 0, wx.EXPAND | wx.ALL, m)

        # --- luz
        caixa = wx.StaticBoxSizer(wx.VERTICAL, painel, "Luz")
        cx = caixa.GetStaticBox()
        topo = wx.BoxSizer(wx.HORIZONTAL)
        self.previa = Previa(cx)
        topo.Add(self.previa, 0, wx.RIGHT, m)

        direita = wx.BoxSizer(wx.VERTICAL)
        # fileira fixa: o WrapSizer calcula mal a altura dentro do StaticBox e esconde o que quebra linha
        grade = wx.BoxSizer(wx.HORIZONTAL)
        self.bolinhas = []
        for nome, rgb in PRESETS:
            b = Bolinha(cx, rgb, nome, self.definir_cor)
            self.bolinhas.append(b)
            grade.Add(b, 0, wx.RIGHT, self.FromDIP(2))
        direita.Add(grade, 0, wx.BOTTOM, e)
        botoes = wx.BoxSizer(wx.HORIZONTAL)
        bt = wx.Button(cx, label="Outra cor…")
        bt.Bind(wx.EVT_BUTTON, self.on_escolher_cor)
        botoes.Add(bt, 0, wx.RIGHT, e)
        self.bt_ligar = wx.ToggleButton(cx, label="Apagar")
        self.bt_ligar.Bind(wx.EVT_TOGGLEBUTTON, self.on_apagar)
        botoes.Add(self.bt_ligar, 0, wx.RIGHT, e)
        self.hex = wx.StaticText(cx)
        self.hex.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        botoes.Add(self.hex, 0, wx.ALIGN_CENTER_VERTICAL)
        direita.Add(botoes)
        topo.Add(direita, 1, wx.ALIGN_CENTER_VERTICAL)
        caixa.Add(topo, 0, wx.EXPAND | wx.ALL, e)

        self.slider_brilho, linha = self._slider(cx, "Brilho", cfg["brilho"], 1, 100, self.aplicar_luz, "%")
        caixa.Add(linha, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        # --- pisca: sequência de cores em ciclo, como fileira de bolinhas
        # cada passo: [r, g, b, segundos]; (0, 0, 0) é uma pausa com a luz apagada
        self.passos = [list(p) for p in cfg["sequencia"]]
        linha = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_piscar = wx.CheckBox(cx, label="Piscar", size=wx.Size(self.col, -1))
        self.chk_piscar.SetValue(cfg["piscar"])
        self.chk_piscar.Bind(wx.EVT_CHECKBOX, self.on_piscar)
        # alinhado ao centro da primeira fileira de bolinhas
        linha.Add(self.chk_piscar, 0, wx.TOP, self.FromDIP(8))
        self.ed_cores = EditorSequencia(
            self, cx, self.passos,
            desenhar=lambda gc, x, y, d, p, alfa: desenhar_bolinha(gc, x, y, d, p[:3], alfa),
            dica=lambda p: ("Pausa (apagada)" if tuple(p[:3]) == APAGADO
                            else "#{:02X}{:02X}{:02X}".format(*p[:3])) + f", {p[3]:.2f} s",
            rotulo=lambda p: segundos(p[3]),
            dica_adicionar="Adicionar cor ou pausa",
            preencher=self.detalhe_cor,
            novos=[("Cor…", self.nova_cor), ("Pausa (apagada)", lambda: [*APAGADO, 0.5])],
            ao_mudar=self.aplicar_pisca,
            ao_mudar_ciclo=self.ressincronizar,
        )
        linha.Add(self.ed_cores.faixa)
        caixa.Add(linha, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, e)
        raiz.Add(caixa, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, m)

        # --- vibração
        caixa = wx.StaticBoxSizer(wx.VERTICAL, painel, "Vibração")
        cx = caixa.GetStaticBox()
        self.slider_forte, linha = self._slider(cx, "Motor forte", cfg["forte"], 0, 255, self.agendar_salvar)
        caixa.Add(linha, 0, wx.EXPAND | wx.ALL, e)
        self.slider_fraco, linha = self._slider(cx, "Motor fraco", cfg["fraco"], 0, 255, self.agendar_salvar)
        caixa.Add(linha, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        linha = wx.BoxSizer(wx.HORIZONTAL)
        linha.Add(wx.StaticText(cx, label="Duração (s)", size=wx.Size(self.col, -1)), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_duracao = self._spin(cx, cfg["duracao"], 0.1, 10.0, 0.1)
        self.spin_duracao.Bind(wx.EVT_SPINCTRLDOUBLE, lambda ev: self.agendar_salvar())
        linha.Add(self.spin_duracao)
        linha.AddStretchSpacer()
        # cada botão vira "Parar" enquanto o que ele começou está tocando (ver acompanhar)
        self.bt_vibrar = wx.Button(cx, label=self.ROTULO_VIBRAR)
        self.bt_vibrar.SetDefault()
        self.bt_vibrar.Bind(wx.EVT_BUTTON, self.on_vibrar)
        linha.Add(self.bt_vibrar)
        caixa.Add(linha, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        caixa.Add(wx.StaticLine(cx), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        # padrão de vibração: passos [forte, fraco, segundos], como a sequência do pisca
        self.padrao = [list(p) for p in cfg["padrao_vibracao"]]
        linha = wx.BoxSizer(wx.HORIZONTAL)
        rotulo = wx.StaticText(cx, label="Padrão", size=wx.Size(self.col, -1))
        linha.Add(rotulo, 0, wx.TOP, self.FromDIP(8))
        self.ed_vib = EditorSequencia(
            self, cx, self.padrao,
            desenhar=lambda gc, x, y, d, p, alfa: desenhar_vibracao(gc, x, y, d, p[0], p[1], alfa),
            dica=lambda p: ("Pausa" if p[0] == p[1] == 0 else f"Forte {p[0]}, fraco {p[1]}") + f", {p[2]:.2f} s",
            rotulo=lambda p: segundos(p[2]),
            dica_adicionar="Adicionar vibração ou pausa",
            preencher=self.detalhe_vibracao,
            novos=[("Vibração (valores dos motores acima)",
                    lambda: [self.slider_forte.GetValue(), self.slider_fraco.GetValue(), 0.3]),
                   ("Pausa", lambda: [0, 0, 0.3])],
            ao_mudar=self.aplicar_padrao,
            ao_mudar_ciclo=self.ressincronizar,
        )
        linha.Add(self.ed_vib.faixa)
        caixa.Add(linha, 0, wx.LEFT | wx.RIGHT, e)
        linha = wx.BoxSizer(wx.HORIZONTAL)
        linha.AddSpacer(self.col)
        self.chk_repetir = wx.CheckBox(cx, label="Repetir até parar")
        self.chk_repetir.SetValue(cfg["repetir_padrao"])
        self.chk_repetir.Bind(wx.EVT_CHECKBOX, self.on_repetir)
        linha.Add(self.chk_repetir, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, m)
        self.chk_sincronizar = wx.CheckBox(cx, label="Sincronizar com a luz")
        self.chk_sincronizar.SetToolTip("Ligar o pisca ou tocar o padrão faz os dois começarem no mesmo "
                                        "instante; depois cada um segue o próprio ciclo.")
        self.chk_sincronizar.SetValue(cfg["sincronizar"])
        self.chk_sincronizar.Bind(wx.EVT_CHECKBOX, lambda ev: self.agendar_salvar())
        linha.Add(self.chk_sincronizar, 0, wx.ALIGN_CENTER_VERTICAL)
        linha.AddStretchSpacer()
        self.bt_tocar = wx.Button(cx, label=self.ROTULO_TOCAR)
        self.bt_tocar.Bind(wx.EVT_BUTTON, self.on_tocar)
        linha.Add(self.bt_tocar)
        caixa.Add(linha, 0, wx.EXPAND | wx.ALL, e)
        raiz.Add(caixa, 0, wx.EXPAND | wx.ALL, m)

        # os dois botões têm a mesma largura e não mudam de tamanho ao virar "Parar"
        largura = max(self.bt_tocar.GetBestSize().width, self.FromDIP(110))
        largura = max(largura, self.bt_tocar.GetTextExtent(self.ROTULO_TOCAR).width + self.FromDIP(32))
        for bt in (self.bt_vibrar, self.bt_tocar):
            bt.SetMinSize(wx.Size(largura, -1))

        painel.SetSizer(raiz)
        raiz.SetSizeHints(self)
        self.Bind(wx.EVT_CLOSE, self.on_fechar)

        self.aplicar_luz()
        self.aplicar_padrao()

        # acompanha o que está tocando no controle: destaca o passo e troca os botões por "Parar"
        self.andamento = (None, None, False)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda ev: self.acompanhar())
        self.timer.Start(50)

    ROTULO_VIBRAR = "Vibrar"
    ROTULO_TOCAR = "Tocar padrão"

    def acompanhar(self):
        if not self.IsShown():
            return
        andamento = self.g.andamento()
        if andamento == self.andamento:
            return
        self.andamento = andamento
        passo_cor, passo_vib, simples = andamento
        self.ed_cores.faixa.tocar(passo_cor)
        self.ed_vib.faixa.tocar(passo_vib)
        self.bt_vibrar.SetLabel("Parar" if simples else self.ROTULO_VIBRAR)
        self.bt_tocar.SetLabel("Parar" if passo_vib is not None else self.ROTULO_TOCAR)

    def reajustar(self):
        self.painel.Layout()
        self.painel.GetSizer().SetSizeHints(self)

    def _slider(self, pai, rotulo, valor, minimo, maximo, ao_mudar, sufixo=""):
        """Linha 'rótulo  [-----o----]  [valor]'. O valor pode ser arrastado ou digitado; os dois
        ficam sincronizados. Devolve (slider, sizer)."""
        linha = wx.BoxSizer(wx.HORIZONTAL)
        texto = wx.StaticText(pai, label=rotulo, size=wx.Size(self.col, -1))
        linha.Add(texto, 0, wx.ALIGN_CENTER_VERTICAL)
        slider = wx.Slider(pai, value=valor, minValue=minimo, maxValue=maximo,
                           size=pai.FromDIP(wx.Size(200, -1)))
        linha.Add(slider, 1, wx.ALIGN_CENTER_VERTICAL)
        campo = wx.SpinCtrl(pai, value=str(valor), min=minimo, max=maximo,
                            size=largura_campo(pai, 62), style=wx.SP_ARROW_KEYS | wx.TE_PROCESS_ENTER)
        # o campo encosta na margem direita; a unidade vai no rótulo, para os campos ficarem alinhados
        linha.Add(campo, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(4))
        if sufixo:
            texto.SetLabel(f"{rotulo} ({sufixo})")

        def do_slider(_):
            campo.SetValue(slider.GetValue())
            ao_mudar()

        def do_campo(_):
            # SpinCtrl já limita ao intervalo; EVT_SPINCTRL vem das setas, Enter ou ao sair do campo
            if campo.GetValue() != slider.GetValue():
                slider.SetValue(campo.GetValue())
                ao_mudar()

        slider.Bind(wx.EVT_SLIDER, do_slider)
        campo.Bind(wx.EVT_SPINCTRL, do_campo)
        campo.Bind(wx.EVT_TEXT_ENTER, do_campo)
        slider.campo = campo  # para mudar os dois juntos por código (ver aplicar_preset)
        return slider, linha

    @staticmethod
    def _spin(pai, valor, minimo, maximo, passo):
        s = wx.SpinCtrlDouble(pai, value=str(valor), min=minimo, max=maximo, inc=passo,
                              size=largura_campo(pai, 70))
        s.SetDigits(2)
        return s

    # --- ações

    def definir_cor(self, rgb):
        self.cor = tuple(rgb)
        self.ligada = True
        self.aplicar_luz()

    def escolher_cor(self, inicial):
        """Abre o seletor de cor do Windows; devolve (r, g, b) ou None se cancelar."""
        dados = wx.ColourData()
        dados.SetColour(wx.Colour(*inicial))
        dados.SetChooseFull(True)
        with wx.ColourDialog(self, dados) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            c = dlg.GetColourData().GetColour()
            return c.Red(), c.Green(), c.Blue()

    def on_escolher_cor(self, _):
        rgb = self.escolher_cor(self.cor)
        if rgb:
            self.definir_cor(rgb)

    # --- sequência do pisca e padrão de vibração (detalhes de cada passo)

    def _campos(self, painel, raiz, campos):
        """Grade 'rótulo [campo] unidade' do balão de detalhe."""
        grade = wx.FlexGridSizer(cols=3, vgap=self.FromDIP(4), hgap=self.FromDIP(4))
        for rotulo, campo, unidade in campos:
            grade.Add(wx.StaticText(painel, label=rotulo), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(2))
            grade.Add(campo)
            grade.Add(wx.StaticText(painel, label=unidade), 0, wx.ALIGN_CENTER_VERTICAL)
        raiz.Add(grade, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(6))

    @staticmethod
    def _ao_digitar(campo, converter, minimo, maximo, aplicar):
        """Aplica o valor a cada tecla (sem esperar Enter ou sair do campo), se ele for válido."""
        def digitou(ev):
            try:
                valor = converter(ev.GetString().replace(",", "."))
            except ValueError:
                return
            if minimo <= valor <= maximo:
                aplicar(valor)
        campo.Bind(wx.EVT_TEXT, digitou)

    def _campo_duracao(self, painel, editor, i, indice):
        def mudou(valor):
            editor.mudar_campo(i, indice, valor)
            self.ressincronizar()

        spin = self._spin(painel, editor.itens[i][indice], 0.05, 10.0, 0.05)
        spin.Bind(wx.EVT_SPINCTRLDOUBLE, lambda ev: mudou(ev.GetValue()))
        self._ao_digitar(spin, float, 0.05, 10.0, mudou)
        return spin

    def ressincronizar(self):
        """Com "Sincronizar com a luz", mudar uma duração ou adicionar, duplicar ou remover um passo
        recomeça os dois juntos, como ao ligar o pisca (sem isso, o ciclo muda de tamanho e cada um
        salta para um ponto qualquer)."""
        if not self.chk_sincronizar.IsChecked():
            return
        if self.chk_piscar.IsChecked() or self.andamento[1] is not None:
            self.g.tocar_padrao(self.chk_repetir.IsChecked(), com_pisca=True)
            self.acompanhar()

    def detalhe_cor(self, balao, painel, raiz, i):
        r, g, b, _ = self.passos[i]
        rgb = (r, g, b)
        dica = "Trocar por uma cor" if rgb == APAGADO else "Trocar a cor"
        bolinha = Bolinha(painel, rgb, dica, lambda _: balao.acao(self.trocar_cor_passo, i))
        sub = "Pausa (apagada)" if rgb == APAGADO else "#{:02X}{:02X}{:02X}".format(*rgb)
        DetalhePasso.titulo(painel, raiz, bolinha, f"Passo {i + 1} de {len(self.passos)}", sub)
        self._campos(painel, raiz, [("Duração (s)", self._campo_duracao(painel, self.ed_cores, i, 3), "")])

    def nova_cor(self):
        rgb = self.escolher_cor(self.cor)
        return [*rgb, 0.5] if rgb else None

    def trocar_cor_passo(self, i):
        atual = tuple(self.passos[i][:3])
        rgb = self.escolher_cor(self.cor if atual == APAGADO else atual)
        if rgb:
            self.passos[i][:3] = rgb
            self.ed_cores.alterar()
        self.ed_cores.reabrir(i)

    def detalhe_vibracao(self, balao, painel, raiz, i):
        passo = self.padrao[i]
        mini = Miniatura(painel, lambda gc, x, y, d: desenhar_vibracao(gc, x, y, d, passo[0], passo[1]))
        sub = "Pausa" if passo[0] == passo[1] == 0 else "Vibração"
        DetalhePasso.titulo(painel, raiz, mini, f"Passo {i + 1} de {len(self.padrao)}", sub)
        campos = []
        for rotulo, indice in (("Motor forte", 0), ("Motor fraco", 1)):
            campo = wx.SpinCtrl(painel, value=str(passo[indice]), min=0, max=255,
                                size=largura_campo(painel, 70), style=wx.SP_ARROW_KEYS | wx.TE_PROCESS_ENTER)

            def mudou(ev, campo=campo, indice=indice):
                self.ed_vib.mudar_campo(i, indice, campo.GetValue())
                mini.Refresh()

            campo.Bind(wx.EVT_SPINCTRL, mudou)
            campo.Bind(wx.EVT_TEXT_ENTER, mudou)

            def digitou(valor, indice=indice):
                self.ed_vib.mudar_campo(i, indice, valor)
                mini.Refresh()

            self._ao_digitar(campo, int, 0, 255, digitou)
            campos.append((rotulo, campo, ""))
        campos.append(("Duração (s)", self._campo_duracao(painel, self.ed_vib, i, 2), ""))
        self._campos(painel, raiz, campos)

    def aplicar_padrao(self):
        self.g.padrao_vibracao(self.padrao)
        self.agendar_salvar()

    def on_repetir(self, _):
        self.g.repetir_padrao(self.chk_repetir.IsChecked())
        self.agendar_salvar()

    def on_apagar(self, _):
        self.ligada = not self.bt_ligar.GetValue()
        self.aplicar_luz()

    def aplicar_luz(self):
        efetiva = com_brilho(self.cor, self.slider_brilho.GetValue()) if self.ligada else APAGADO
        # na tela aparece "off"; no controle vai o tom mais escuro da cor (ver tom_apagado)
        self.g.luz(efetiva if self.ligada else tom_apagado(self.cor))
        self.bt_ligar.SetValue(not self.ligada)
        self.bt_ligar.SetLabel("Acender" if not self.ligada else "Apagar")
        for b in self.bolinhas:
            b.selecionar(b.rgb == self.cor)
        self.previa.definir(efetiva)
        self.hex.SetLabel("#{:02X}{:02X}{:02X}".format(*self.cor))
        self.icone = criar_icone(efetiva)
        self.SetIcon(self.icone)
        self._atualizar_bandeja()
        self.aplicar_pisca()  # o brilho e o Apagar valem também para a sequência

    def aplicar_pisca(self):
        brilho = self.slider_brilho.GetValue()
        com_brilho_aplicado = [[*com_brilho((r, g, b), brilho), seg] for r, g, b, seg in self.passos]
        self.g.sequencia(sequencia_para_envio(com_brilho_aplicado, self.ligada, self.cor))
        if self.chk_piscar.IsChecked():
            self.g.piscar()
        else:
            self.g.parar_pisca()
        self.agendar_salvar()

    def on_vibrar(self, _):
        if self.andamento[2]:
            self.g.parar_vibracao()
        else:
            self.g.vibrar(self.slider_forte.GetValue(), self.slider_fraco.GetValue(), self.spin_duracao.GetValue())
        self.acompanhar()

    def on_piscar(self, _):
        self.aplicar_pisca()
        if self.chk_piscar.IsChecked() and self.chk_sincronizar.IsChecked():
            # o pisca acabou de começar: o padrão começa no mesmo instante
            self.g.tocar_padrao(self.chk_repetir.IsChecked(), com_pisca=True)
            self.acompanhar()

    def on_tocar(self, _):
        if self.andamento[1] is not None:
            self.g.parar_vibracao()
        else:
            self.g.tocar_padrao(self.chk_repetir.IsChecked(), com_pisca=self.chk_sincronizar.IsChecked())
        self.acompanhar()

    def conexao_mudou(self, conectado, bluetooth):
        """Chamado da thread do controle; só mexe na GUI via wx.CallAfter."""
        wx.CallAfter(self._mostrar_conexao, conectado, bluetooth)

    def bateria_mudou(self, porcentagem, no_cabo):
        """Chamado da thread do controle; só mexe na GUI via wx.CallAfter."""
        wx.CallAfter(self._mostrar_bateria, porcentagem, no_cabo)

    def _mostrar_bateria(self, porcentagem, no_cabo):
        self.bateria.definir(porcentagem, no_cabo)
        self._atualizar_bandeja()

    def _atualizar_bandeja(self):
        """Ícone na cor da luz; a dica do ícone mostra a bateria."""
        p = self.bateria.porcentagem
        dica = TITULO if p is None else f"{TITULO}: bateria {p}%" + (" (carregando)" if self.bateria.no_cabo else "")
        self.bandeja.SetIcon(self.icone, dica)

    def _mostrar_conexao(self, conectado, bluetooth):
        if conectado:
            self.status.SetLabel(f"Conectado via {'Bluetooth' if bluetooth else 'USB'}")
            self.indicador.definir(COR_CONECTADO)
        else:
            self.status.SetLabel("Controle desconectado. Procurando…")
            self.indicador.definir(COR_DESCONECTADO)

    # --- configurações

    def agendar_salvar(self):
        # sliders disparam muitos eventos; salva meio segundo depois do último
        self._salvar_depois.Start(500)

    def salvar_config(self):
        self.cfg.update(
            cor=list(self.cor), brilho=self.slider_brilho.GetValue(), piscar=self.chk_piscar.IsChecked(),
            sequencia=[list(p) for p in self.passos],
            forte=self.slider_forte.GetValue(), fraco=self.slider_fraco.GetValue(),
            duracao=self.spin_duracao.GetValue(),
            padrao_vibracao=[list(p) for p in self.padrao], repetir_padrao=self.chk_repetir.IsChecked(),
            sincronizar=self.chk_sincronizar.IsChecked(),
        )
        config.salvar(self.cfg)

    # --- presets (.lumen.json)

    def menu_opcoes(self, botao):
        """Menu do botão '⋯' do cabeçalho, aberto logo abaixo dele."""
        menu = wx.Menu()
        for rotulo, acao in (("Importar preset…", self.on_importar), ("Exportar preset…", self.on_exportar),
                             (None, None), (f"Sobre o {TITULO}", self.on_sobre)):
            if rotulo is None:
                menu.AppendSeparator()
            else:
                self.Bind(wx.EVT_MENU, acao, menu.Append(wx.ID_ANY, rotulo))
        botao.PopupMenu(menu, wx.Point(0, botao.GetSize().height))
        menu.Destroy()
        botao._sobre(False)  # o mouse saiu enquanto o menu estava aberto

    def on_sobre(self, _):
        info = wx.adv.AboutDialogInfo()
        info.SetName(TITULO)
        info.SetVersion(versao.VERSAO)
        info.SetDescription("Luz, pisca, vibração e bateria para controles de PS4\n(inclusive paralelos).")
        info.SetWebSite(versao.REPOSITORIO)
        info.SetIcon(self.icone)
        wx.adv.AboutBox(info, self)

    CURINGA_PRESET = f"Preset do Lumen (*{preset.EXTENSAO})|*{preset.EXTENSAO}|JSON (*.json)|*.json"

    def on_exportar(self, _):
        with wx.FileDialog(self, "Exportar preset", wildcard=self.CURINGA_PRESET, defaultFile=f"meu preset{preset.EXTENSAO}",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            caminho = dlg.GetPath()
        nome = os.path.basename(caminho)
        for sufixo in (preset.EXTENSAO, ".json"):
            if nome.lower().endswith(sufixo):
                nome = nome[:-len(sufixo)]
                break
        self.salvar_config()  # deixa self.cfg igual à tela
        try:
            preset.salvar(caminho, self.cfg, nome)
        except OSError as e:
            wx.MessageBox(f"Não consegui salvar o preset.\n\n{e}", TITULO, wx.OK | wx.ICON_ERROR, self)
            return
        logging.info("preset exportado: %s", caminho)

    def on_importar(self, _):
        with wx.FileDialog(self, "Importar preset", wildcard=self.CURINGA_PRESET,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            caminho = dlg.GetPath()
        try:
            mudancas, nome, avisos = preset.carregar(caminho)
        except preset.PresetInvalido as e:
            wx.MessageBox(f"Esse arquivo não pôde ser importado: {e}.\nNada foi alterado.",
                          TITULO, wx.OK | wx.ICON_ERROR, self)
            return
        self.aplicar_preset(mudancas)
        logging.info("preset importado: %s (%d campos, %d avisos)", caminho, len(mudancas), len(avisos))
        if avisos:
            wx.MessageBox(f"Preset “{nome or os.path.basename(caminho)}” importado, com avisos:\n\n• "
                          + "\n• ".join(avisos), TITULO, wx.OK | wx.ICON_WARNING, self)

    def aplicar_preset(self, m):
        """Aplica as mudanças de um preset (chaves do config.py; só as presentes) na tela e no controle."""
        for editor in (self.ed_cores, self.ed_vib):
            if editor.detalhe:
                editor.detalhe.fechar()
        if "cor" in m:
            self.cor = tuple(m["cor"])
            self.ligada = True
        for chave, slider in (("brilho", self.slider_brilho), ("forte", self.slider_forte),
                              ("fraco", self.slider_fraco)):
            if chave in m:
                slider.SetValue(m[chave])
                slider.campo.SetValue(m[chave])
        if "duracao" in m:
            self.spin_duracao.SetValue(m["duracao"])
        for chave, caixa in (("piscar", self.chk_piscar), ("repetir_padrao", self.chk_repetir),
                             ("sincronizar", self.chk_sincronizar)):
            if chave in m:
                caixa.SetValue(m[chave])
        # as listas são compartilhadas com os editores: troca o conteúdo, não a lista
        if "sequencia" in m:
            self.passos[:] = [list(p) for p in m["sequencia"]]
            self.ed_cores.faixa.atualizar()
        if "padrao_vibracao" in m:
            self.padrao[:] = [list(p) for p in m["padrao_vibracao"]]
            self.ed_vib.faixa.atualizar()
        self.reajustar()

        self.g.repetir_padrao(self.chk_repetir.IsChecked())
        self.g.parar_pisca()  # a sequência nova começa do primeiro passo
        self.aplicar_luz()    # aplica também o pisca e agenda salvar
        self.aplicar_padrao()
        if self.chk_piscar.IsChecked() and self.chk_sincronizar.IsChecked():
            self.g.tocar_padrao(self.chk_repetir.IsChecked(), com_pisca=True)
        self.acompanhar()

    # --- janela e bandeja

    def mostrar(self):
        self.Show()
        self.Iconize(False)
        self.Raise()

    def on_fechar(self, evento):
        if self.saindo or not evento.CanVeto():
            evento.Skip()
            return
        if not wx.adv.TaskBarIcon.IsAvailable():
            # sem bandeja (alguns ambientes Linux), esconder a janela deixaria o app inalcançável
            self.sair()
            return
        evento.Veto()
        self.Hide()
        if not self.avisou_bandeja and hasattr(self.bandeja, "ShowBalloon"):  # balão só existe no Windows
            self.avisou_bandeja = True
            self.bandeja.ShowBalloon(TITULO, "Continua rodando na bandeja. Use Sair no ícone para encerrar.")

    def sair(self):
        self.saindo = True
        self.timer.Stop()
        self._salvar_depois.Stop()
        self.salvar_config()
        self.g.encerrar()
        self.bandeja.RemoveIcon()
        self.bandeja.Destroy()
        self.Destroy()


def declarar_dpi():
    """Avisa o Windows que o app cuida da própria escala; sem isso, com escala acima de 100%,
    o Windows desenha a janela em 100% e estica a imagem (letras borradas). O pythonw.exe não
    declara isso no manifesto, então é feito aqui, antes de criar qualquer janela. No Linux o GTK
    já cuida disso."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except (AttributeError, OSError):
            pass


def configurar_log():
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=config.PASTA_DADOS / "lumen.log", encoding="utf-8", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def smoke_test():
    """--smoke-test: abre a janela de verdade, exercita o desenho e o balão de detalhe e sai sozinho.

    Não toca no controle (a thread do gerenciador não começa), não usa a instância única e não salva
    nada. Usado no CI para garantir que o app abre em cada sistema; sai com 0 se tudo deu certo.
    """
    erros = []

    def registrar(tipo, valor, tb):
        # exceções dentro de eventos do wx não derrubam o MainLoop; aqui elas reprovam o teste
        traceback.print_exception(tipo, valor, tb)
        erros.append(valor)

    sys.excepthook = registrar
    config.salvar = lambda dados: None
    declarar_dpi()
    app = wx.App(False)
    janela = Janela(Gerenciador(), dict(config.PADRAO))
    janela.Show()
    resultado = []

    def exercitar():
        try:
            janela._mostrar_conexao(True, True)
            janela._mostrar_bateria(80, False)
            janela.acompanhar()
            janela.ed_cores.abrir_detalhe(0)
            janela.ed_vib.abrir_detalhe(0)
        except Exception:
            registrar(*sys.exc_info())
        finally:
            # sempre encerra, com ou sem erro (senão a janela ficaria aberta até o CI matar)
            wx.CallLater(500, terminar)

    def terminar():
        if resultado:
            return
        try:
            for editor in (janela.ed_cores, janela.ed_vib):
                if editor.detalhe:
                    editor.detalhe.fechar()
        except Exception:
            registrar(*sys.exc_info())
        ok = janela.IsShown() and not erros
        print(f"smoke test: {'ok' if ok else f'falhou ({len(erros)} erro(s))'}")
        resultado.append(0 if ok else 1)
        janela.sair()

    def estourou():
        # rede de segurança: se algo travar o fluxo acima, falha com mensagem clara
        if not resultado:
            print("smoke test: falhou (não terminou em 30 s)")
            resultado.append(1)
            wx.GetApp().ExitMainLoop()

    wx.CallLater(1500, exercitar)
    wx.CallLater(30000, estourou)
    app.MainLoop()
    return resultado[0] if resultado else 1


def main():
    if "--version" in sys.argv[1:]:
        # sem abrir janela nem tocar no controle (usado também no teste do build)
        print(f"{TITULO} {versao.VERSAO}")
        return 0
    if "--smoke-test" in sys.argv[1:]:
        return smoke_test()
    configurar_log()
    inst = instancia.Instancia()
    if not inst.principal:
        if sys.platform == "win32":
            # deixa a instância principal trazer a própria janela para a frente
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        if not instancia.avisar("mostrar"):
            logging.warning("já existe uma instância, mas não consegui avisá-la")
        return

    logging.info("iniciando %s %s", TITULO, versao.VERSAO)
    declarar_dpi()
    app = wx.App()
    janela = None

    g = Gerenciador(ao_mudar_conexao=lambda c, bt: janela and janela.conexao_mudou(c, bt),
                    ao_mudar_bateria=lambda p, cabo: janela and janela.bateria_mudou(p, cabo))
    janela = Janela(g, config.carregar())
    logging.info("escala da tela: %.0f%%", janela.GetDPIScaleFactor() * 100)

    def ao_receber(msg):
        logging.info("mensagem de outra instância: %s", msg)
        if msg == "mostrar":
            wx.CallAfter(janela.mostrar)

    inst.ouvir(ao_receber)
    g.iniciar()
    janela.Show()
    app.MainLoop()
    logging.info("encerrado")


if __name__ == "__main__":
    sys.exit(main())

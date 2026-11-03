"""Programa com GUI (wxPython) que é o dono do controle DS4: luz, pisca e vibração.

Fechar a janela minimiza para a bandeja; o programa só encerra pelo "Sair" no ícone da bandeja.
Abrir o programa de novo só traz a janela da instância que já está rodando.

Uso (desenvolvimento): .\.venv\Scripts\pythonw.exe app.py
"""
import ctypes
import logging
import math
import sys

import wx
import wx.adv

import config
import instancia
from gerenciador import Gerenciador

TITULO = "Controle DS4"

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


class Faixa(wx.Control):
    """Sequência do pisca como uma fileira de bolinhas.

    Clique numa bolinha abre o detalhe dela; arrastar muda a ordem; a última bolinha ('+') adiciona.
    A lista `passos` ([r, g, b, segundos]) é a mesma da janela, compartilhada.
    """

    POR_LINHA = 9
    LIMIAR_ARRASTO = 4  # px que o mouse precisa andar para virar arrasto

    def __init__(self, pai, passos, ao_clicar, ao_mover, ao_adicionar):
        super().__init__(pai, style=wx.BORDER_NONE)
        self.passos = passos
        self.ao_clicar = ao_clicar        # (indice, retangulo_na_tela)
        self.ao_mover = ao_mover          # (origem, posicao_de_insercao)
        self.ao_adicionar = ao_adicionar  # (retangulo_na_tela)
        self.selecionado = None
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

    @property
    def tam(self):
        return self.FromDIP(32)

    def _n(self):
        return len(self.passos) + 1  # + a bolinha de adicionar

    def DoGetBestSize(self):
        linhas = (self._n() + self.POR_LINHA - 1) // self.POR_LINHA
        return wx.Size(self.POR_LINHA * self.tam, linhas * self.tam)

    def atualizar(self):
        self.InvalidateBestSize()
        self.Refresh()

    def _ret(self, i):
        linha, col = divmod(i, self.POR_LINHA)
        return wx.Rect(col * self.tam, linha * self.tam, self.tam, self.tam)

    def _indice_em(self, pt):
        col, linha = pt.x // self.tam, pt.y // self.tam
        i = linha * self.POR_LINHA + col
        return i if 0 <= col < self.POR_LINHA and 0 <= i < self._n() else None

    def _insercao(self, pt):
        """Posição (0..len) onde o item arrastado entraria se soltasse em pt."""
        linhas = max(1, (len(self.passos) + self.POR_LINHA - 1) // self.POR_LINHA)
        linha = max(0, min(linhas - 1, pt.y // self.tam))
        col = max(0, min(self.POR_LINHA, round(pt.x / self.tam)))
        return max(0, min(len(self.passos), linha * self.POR_LINHA + col))

    def _na_tela(self, i):
        r = self._ret(i)
        return wx.Rect(self.ClientToScreen(r.GetTopLeft()), r.GetSize())

    def _definir_sobre(self, i):
        if i != self.sobre:
            self.sobre = i
            if i is not None and i < len(self.passos):
                self.SetToolTip(f"{self.passos[i][3]:.2f} s")
            else:
                self.SetToolTip("Adicionar cor ou pausa" if i is not None else None)
            self.Refresh()

    def on_down(self, ev):
        i = self._indice_em(ev.GetPosition())
        if i is None:
            return
        self.pressionado = i
        self.inicio_arrasto = ev.GetPosition()
        if i < len(self.passos):
            self.CaptureMouse()

    def on_motion(self, ev):
        self.mouse = ev.GetPosition()
        if self.pressionado is None or self.pressionado >= len(self.passos) or not ev.LeftIsDown():
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
            if i < len(self.passos):
                self.ao_clicar(i, self._na_tela(i))
            else:
                self.ao_adicionar(self._na_tela(i))

    def _cancelar(self):
        if self.HasCapture():
            self.ReleaseMouse()
        self.pressionado = None
        self.arrastando = False
        self.Refresh()

    def on_paint(self, _):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        tam = self.tam
        folga = self.FromDIP(4)
        anel = self.FromDIP(2)
        destaque = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        for i, (r, g, b, _) in enumerate(self.passos):
            x, y = self._ret(i).GetTopLeft()
            if i in (self.selecionado, self.sobre) and not self.arrastando:
                alfa = 255 if i == self.selecionado else 110
                gc.SetPen(wx.Pen(wx.Colour(destaque.Red(), destaque.Green(), destaque.Blue(), alfa), anel))
                gc.SetBrush(wx.TRANSPARENT_BRUSH)
                gc.DrawEllipse(x + anel / 2, y + anel / 2, tam - anel, tam - anel)
            # o item sendo arrastado fica "fantasma" no lugar de origem
            alfa = 70 if self.arrastando and i == self.pressionado else 255
            desenhar_bolinha(gc, x + folga, y + folga, tam - 2 * folga, (r, g, b), alfa)

        # bolinha de adicionar: contorno tracejado com '+'
        x, y = self._ret(len(self.passos)).GetTopLeft()
        cinza = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        if self.sobre == len(self.passos):
            cinza = destaque
        caneta = wx.Pen(cinza, self.FromDIP(1), wx.PENSTYLE_SHORT_DASH)
        gc.SetPen(caneta)
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawEllipse(x + folga, y + folga, tam - 2 * folga, tam - 2 * folga)
        c, braco = tam / 2, tam / 5
        gc.SetPen(wx.Pen(cinza, self.FromDIP(2)))
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
            if col == 0 and pos > 0 and pos == len(self.passos) and pos % self.POR_LINHA == 0:
                linha, col = linha - 1, self.POR_LINHA
            bx, by = col * tam, linha * tam
            gc.SetPen(wx.Pen(destaque, self.FromDIP(3)))
            gc.StrokeLine(bx, by + folga, bx, by + tam - folga)
            r, g, b, _ = self.passos[self.pressionado]
            d = tam - 2 * folga
            desenhar_bolinha(gc, self.mouse.x - d / 2, self.mouse.y - d / 2, d, (r, g, b), 200)


class DetalhePasso(wx.PopupTransientWindow):
    """Balão com o detalhe de uma cor da sequência: trocar cor, duração, ordem e remover."""

    def __init__(self, janela, i):
        super().__init__(janela, wx.BORDER_SIMPLE)
        self.janela = janela
        self.i = i
        r, g, b, seg = janela.passos[i]
        rgb = (r, g, b)
        e = self.FromDIP(6)

        painel = wx.Panel(self)
        painel.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        raiz = wx.BoxSizer(wx.VERTICAL)

        topo = wx.BoxSizer(wx.HORIZONTAL)
        dica = "Trocar por uma cor" if rgb == APAGADO else "Trocar a cor"
        topo.Add(Bolinha(painel, rgb, dica, lambda _: self._acao(janela.trocar_cor_passo, i)),
                 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        titulo = wx.StaticText(painel, label=f"Passo {i + 1} de {len(janela.passos)}")
        titulo.SetFont(titulo.GetFont().Bold())
        texto = wx.BoxSizer(wx.VERTICAL)
        texto.Add(titulo)
        sub = wx.StaticText(painel, label="Pausa (apagada)" if rgb == APAGADO else "#{:02X}{:02X}{:02X}".format(*rgb))
        sub.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        texto.Add(sub)
        topo.Add(texto, 0, wx.ALIGN_CENTER_VERTICAL)
        raiz.Add(topo, 0, wx.ALL, e)

        linha = wx.BoxSizer(wx.HORIZONTAL)
        linha.Add(wx.StaticText(painel, label="Duração"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        spin = janela._spin(painel, seg, 0.05, 10.0, 0.05)
        spin.Bind(wx.EVT_SPINCTRLDOUBLE, lambda ev: janela.mudar_tempo_passo(i, ev.GetValue()))
        linha.Add(spin, 0, wx.RIGHT, self.FromDIP(2))
        linha.Add(wx.StaticText(painel, label="s"), 0, wx.ALIGN_CENTER_VERTICAL)
        raiz.Add(linha, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        linha = wx.BoxSizer(wx.HORIZONTAL)
        for rotulo, acao, ativo in (
            ("Antes", lambda ev: self._acao(janela.mover_passo, i, -1), i > 0),
            ("Depois", lambda ev: self._acao(janela.mover_passo, i, +1), i < len(janela.passos) - 1),
            ("Remover", lambda ev: self._acao(janela.remover_passo, i), True),
        ):
            bt = wx.Button(painel, label=rotulo, style=wx.BU_EXACTFIT)
            bt.Bind(wx.EVT_BUTTON, acao)
            bt.Enable(ativo)
            linha.Add(bt, 0, wx.RIGHT, self.FromDIP(4))
        raiz.Add(linha, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        painel.SetSizer(raiz)
        raiz.Fit(painel)
        self.SetClientSize(painel.GetSize())

    def _acao(self, funcao, *args):
        # fecha o balão antes: a ação pode abrir um diálogo ou remontar a sequência
        self.fechar()
        wx.CallAfter(funcao, *args)

    def fechar(self):
        # Dismiss() feito pelo código não chama OnDismiss (só o clique fora chama)
        self.Dismiss()
        self.OnDismiss()

    def OnDismiss(self):
        self.janela.detalhe_fechado(self)


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

        # --- cabeçalho: status da conexão
        linha = wx.BoxSizer(wx.HORIZONTAL)
        self.indicador = Indicador(painel)
        linha.Add(self.indicador, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        self.status = wx.StaticText(painel, label="Procurando controle…")
        linha.Add(self.status, 1, wx.ALIGN_CENTER_VERTICAL)
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
        self.detalhe = None
        linha = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_piscar = wx.CheckBox(cx, label="Piscar", size=cx.FromDIP(wx.Size(78, -1)))
        self.chk_piscar.SetValue(cfg["piscar"])
        self.chk_piscar.Bind(wx.EVT_CHECKBOX, lambda ev: self.aplicar_pisca())
        # alinhado ao centro da primeira fileira de bolinhas
        linha.Add(self.chk_piscar, 0, wx.TOP, self.FromDIP(8))
        self.faixa = Faixa(cx, self.passos, self.abrir_detalhe, self.arrastar_passo, self.menu_adicionar)
        linha.Add(self.faixa)
        caixa.Add(linha, 0, wx.LEFT | wx.RIGHT, e)
        dica = wx.StaticText(cx, label="Clique numa cor para editar; arraste para mudar a ordem.")
        dica.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        dica.SetFont(dica.GetFont().Smaller())
        recuo = wx.BoxSizer(wx.HORIZONTAL)  # alinha a dica com a faixa, sem afetar a margem de baixo
        recuo.AddSpacer(self.FromDIP(78))
        recuo.Add(dica)
        caixa.Add(recuo, 0, wx.LEFT | wx.BOTTOM, e)
        raiz.Add(caixa, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, m)

        # --- vibração
        caixa = wx.StaticBoxSizer(wx.VERTICAL, painel, "Vibração")
        cx = caixa.GetStaticBox()
        self.slider_forte, linha = self._slider(cx, "Motor forte", cfg["forte"], 0, 255, self.agendar_salvar)
        caixa.Add(linha, 0, wx.EXPAND | wx.ALL, e)
        self.slider_fraco, linha = self._slider(cx, "Motor fraco", cfg["fraco"], 0, 255, self.agendar_salvar)
        caixa.Add(linha, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)

        linha = wx.BoxSizer(wx.HORIZONTAL)
        linha.Add(wx.StaticText(cx, label="Duração"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, e)
        self.spin_duracao = self._spin(cx, cfg["duracao"], 0.1, 10.0, 0.1)
        self.spin_duracao.Bind(wx.EVT_SPINCTRLDOUBLE, lambda ev: self.agendar_salvar())
        linha.Add(self.spin_duracao, 0, wx.RIGHT, self.FromDIP(2))
        linha.Add(wx.StaticText(cx, label="s"), 0, wx.ALIGN_CENTER_VERTICAL)
        linha.AddStretchSpacer()
        bt = wx.Button(cx, label="Vibrar")
        bt.SetDefault()
        bt.Bind(wx.EVT_BUTTON, self.on_vibrar)
        linha.Add(bt, 0, wx.RIGHT, e)
        bt = wx.Button(cx, label="Parar")
        bt.Bind(wx.EVT_BUTTON, lambda ev: self.g.parar_vibracao())
        linha.Add(bt)
        caixa.Add(linha, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, e)
        raiz.Add(caixa, 0, wx.EXPAND | wx.ALL, m)

        painel.SetSizer(raiz)
        raiz.SetSizeHints(self)
        self.Bind(wx.EVT_CLOSE, self.on_fechar)

        self.aplicar_luz()

    def _slider(self, pai, rotulo, valor, minimo, maximo, ao_mudar, sufixo=""):
        """Linha 'rótulo  [-----o----]  [valor]'. O valor pode ser arrastado ou digitado; os dois
        ficam sincronizados. Devolve (slider, sizer)."""
        linha = wx.BoxSizer(wx.HORIZONTAL)
        texto = wx.StaticText(pai, label=rotulo, size=pai.FromDIP(wx.Size(78, -1)))
        linha.Add(texto, 0, wx.ALIGN_CENTER_VERTICAL)
        slider = wx.Slider(pai, value=valor, minValue=minimo, maxValue=maximo,
                           size=pai.FromDIP(wx.Size(200, -1)))
        linha.Add(slider, 1, wx.ALIGN_CENTER_VERTICAL)
        campo = wx.SpinCtrl(pai, value=str(valor), min=minimo, max=maximo,
                            size=pai.FromDIP(wx.Size(62, -1)), style=wx.SP_ARROW_KEYS | wx.TE_PROCESS_ENTER)
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
        return slider, linha

    @staticmethod
    def _spin(pai, valor, minimo, maximo, passo):
        s = wx.SpinCtrlDouble(pai, value=str(valor), min=minimo, max=maximo, inc=passo,
                              size=pai.FromDIP(wx.Size(70, -1)))
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

    # --- sequência do pisca

    def alterar_passos(self):
        self.faixa.atualizar()
        self.painel.Layout()
        self.painel.GetSizer().SetSizeHints(self)  # a faixa ganha outra fileira a cada 9 cores
        self.aplicar_pisca()

    def abrir_detalhe(self, i, ret_na_tela):
        if self.detalhe:
            self.detalhe.fechar()
        self.detalhe = DetalhePasso(self, i)
        self.detalhe.Position(ret_na_tela.GetBottomLeft(), wx.Size(0, self.FromDIP(2)))
        self.faixa.selecionado = i
        self.faixa.Refresh()
        self.detalhe.Popup()

    def detalhe_fechado(self, detalhe):
        if detalhe is self.detalhe:
            self.detalhe = None
            self.faixa.selecionado = None
            self.faixa.Refresh()
        wx.CallAfter(detalhe.Destroy)

    def menu_adicionar(self, ret_na_tela):
        menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.on_adicionar_cor, menu.Append(wx.ID_ANY, "Cor…"))
        self.Bind(wx.EVT_MENU, lambda ev: self.adicionar_passo(APAGADO), menu.Append(wx.ID_ANY, "Pausa (apagada)"))
        self.faixa.PopupMenu(menu, self.faixa.ScreenToClient(ret_na_tela.GetBottomLeft()))
        menu.Destroy()

    def adicionar_passo(self, rgb):
        self.passos.append([*rgb, 0.5])
        self.alterar_passos()

    def on_adicionar_cor(self, _):
        rgb = self.escolher_cor(self.cor)
        if rgb:
            self.adicionar_passo(rgb)

    def trocar_cor_passo(self, i):
        atual = tuple(self.passos[i][:3])
        rgb = self.escolher_cor(self.cor if atual == APAGADO else atual)
        if rgb:
            self.passos[i][:3] = rgb
            self.alterar_passos()
        self.reabrir_detalhe(i)

    def mudar_tempo_passo(self, i, segundos):
        self.passos[i][3] = segundos
        self.aplicar_pisca()

    def arrastar_passo(self, origem, insercao):
        """Solta o passo `origem` na posição `insercao` (0..len, contada antes de tirá-lo)."""
        destino = insercao - 1 if insercao > origem else insercao
        if destino != origem:
            self.passos.insert(destino, self.passos.pop(origem))
            self.alterar_passos()

    def mover_passo(self, i, delta):
        j = i + delta
        self.passos[i], self.passos[j] = self.passos[j], self.passos[i]
        self.alterar_passos()
        self.reabrir_detalhe(j)  # o detalhe acompanha a cor na nova posição

    def reabrir_detalhe(self, i):
        if 0 <= i < len(self.passos):
            self.abrir_detalhe(i, self.faixa._na_tela(i))

    def remover_passo(self, i):
        del self.passos[i]
        self.alterar_passos()

    def on_apagar(self, _):
        self.ligada = not self.bt_ligar.GetValue()
        self.aplicar_luz()

    def aplicar_luz(self):
        efetiva = com_brilho(self.cor, self.slider_brilho.GetValue()) if self.ligada else APAGADO
        self.g.luz(efetiva)
        self.bt_ligar.SetValue(not self.ligada)
        self.bt_ligar.SetLabel("Acender" if not self.ligada else "Apagar")
        for b in self.bolinhas:
            b.selecionar(b.rgb == self.cor)
        self.previa.definir(efetiva)
        self.hex.SetLabel("#{:02X}{:02X}{:02X}".format(*self.cor))
        icone = criar_icone(efetiva)
        self.SetIcon(icone)
        self.bandeja.SetIcon(icone, TITULO)
        self.aplicar_pisca()  # o brilho e o Apagar valem também para a sequência

    def aplicar_pisca(self):
        brilho = self.slider_brilho.GetValue()
        efetivos = [(com_brilho((r, g, b), brilho) if self.ligada else APAGADO, seg)
                    for r, g, b, seg in self.passos]
        self.g.sequencia(efetivos)
        if self.chk_piscar.IsChecked():
            self.g.piscar()
        else:
            self.g.parar_pisca()
        self.agendar_salvar()

    def on_vibrar(self, _):
        self.g.vibrar(self.slider_forte.GetValue(), self.slider_fraco.GetValue(), self.spin_duracao.GetValue())

    def conexao_mudou(self, conectado, bluetooth):
        """Chamado da thread do controle; só mexe na GUI via wx.CallAfter."""
        wx.CallAfter(self._mostrar_conexao, conectado, bluetooth)

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
        )
        config.salvar(self.cfg)

    # --- janela e bandeja

    def mostrar(self):
        self.Show()
        self.Iconize(False)
        self.Raise()

    def on_fechar(self, evento):
        if self.saindo or not evento.CanVeto():
            evento.Skip()
            return
        evento.Veto()
        self.Hide()
        if not self.avisou_bandeja:
            self.avisou_bandeja = True
            self.bandeja.ShowBalloon(TITULO, "Continua rodando na bandeja. Use Sair no ícone para encerrar.")

    def sair(self):
        self.saindo = True
        self._salvar_depois.Stop()
        self.salvar_config()
        self.g.encerrar()
        self.bandeja.RemoveIcon()
        self.bandeja.Destroy()
        self.Destroy()


def declarar_dpi():
    """Avisa o Windows que o app cuida da própria escala; sem isso, com escala acima de 100%,
    o Windows desenha a janela em 100% e estica a imagem (letras borradas). O pythonw.exe não
    declara isso no manifesto, então é feito aqui, antes de criar qualquer janela."""
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
        filename=config.PASTA_DADOS / "ds4.log", encoding="utf-8", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main():
    configurar_log()
    inst = instancia.Instancia()
    if not inst.principal:
        # deixa a instância principal trazer a própria janela para a frente
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        if not instancia.avisar("mostrar"):
            logging.warning("já existe uma instância, mas não consegui avisá-la")
        return

    logging.info("iniciando")
    declarar_dpi()
    app = wx.App()
    janela = None

    g = Gerenciador(ao_mudar_conexao=lambda c, bt: janela and janela.conexao_mudou(c, bt))
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

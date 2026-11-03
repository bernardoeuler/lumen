"""Programa com GUI (wxPython) que é o dono do controle DS4: luz, pisca e vibração.

Fechar a janela minimiza para a bandeja; o programa só encerra pelo "Sair" no ícone da bandeja.
Abrir o programa de novo só traz a janela da instância que já está rodando.

Uso (desenvolvimento): .\.venv\Scripts\pythonw.exe app.py
"""
import ctypes
import logging
import math
import os
import sys
from pathlib import Path

import wx
import wx.adv

import instancia
from gerenciador import Gerenciador

TITULO = "Controle DS4"
PASTA_DADOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ds4-cli"

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
    def __init__(self, gerenciador):
        super().__init__(None, title=TITULO, style=wx.DEFAULT_FRAME_STYLE & ~(wx.MAXIMIZE_BOX | wx.RESIZE_BORDER))
        self.g = gerenciador
        self.rgb = APAGADO
        self.saindo = False
        self.avisou_bandeja = False
        self.bandeja = IconeBandeja(self)

        painel = wx.Panel(self)
        raiz = wx.BoxSizer(wx.VERTICAL)

        self.status = wx.StaticText(painel, label="Procurando controle…")
        raiz.Add(self.status, 0, wx.ALL, 10)

        # --- luz
        caixa = wx.StaticBoxSizer(wx.VERTICAL, painel, "Luz")
        linha = wx.BoxSizer(wx.HORIZONTAL)
        # tamanhos fixos em pixels "lógicos" (FromDIP), para acompanharem a escala da tela
        self.amostra = wx.Panel(caixa.GetStaticBox(), size=self.FromDIP(wx.Size(48, 28)), style=wx.BORDER_SIMPLE)
        linha.Add(self.amostra, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        bt = wx.Button(caixa.GetStaticBox(), label="Escolher cor…")
        bt.Bind(wx.EVT_BUTTON, self.on_escolher_cor)
        linha.Add(bt, 0, wx.RIGHT, 6)
        bt = wx.Button(caixa.GetStaticBox(), label="Apagar")
        bt.Bind(wx.EVT_BUTTON, lambda e: self.definir_cor(APAGADO))
        linha.Add(bt)
        caixa.Add(linha, 0, wx.ALL, 6)

        grade = wx.WrapSizer(wx.HORIZONTAL)
        for nome, rgb in PRESETS:
            b = wx.Button(caixa.GetStaticBox(), size=self.FromDIP(wx.Size(28, 28)))
            b.SetBackgroundColour(wx.Colour(*rgb))
            b.SetToolTip(nome)
            b.Bind(wx.EVT_BUTTON, lambda e, c=rgb: self.definir_cor(c))
            grade.Add(b, 0, wx.ALL, 2)
        caixa.Add(grade, 0, wx.ALL, 4)

        linha = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_piscar = wx.CheckBox(caixa.GetStaticBox(), label="Piscar")
        self.chk_piscar.Bind(wx.EVT_CHECKBOX, lambda e: self.aplicar_pisca())
        linha.Add(self.chk_piscar, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.spin_aceso = self._spin(caixa.GetStaticBox(), 0.5, 0.05, 5.0, 0.05)
        self.spin_apagado = self._spin(caixa.GetStaticBox(), 0.5, 0.05, 5.0, 0.05)
        for rotulo, spin in (("aceso (s)", self.spin_aceso), ("apagado (s)", self.spin_apagado)):
            spin.Bind(wx.EVT_SPINCTRLDOUBLE, lambda e: self.aplicar_pisca())
            linha.Add(wx.StaticText(caixa.GetStaticBox(), label=rotulo), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            linha.Add(spin, 0, wx.RIGHT, 10)
        caixa.Add(linha, 0, wx.ALL, 6)
        raiz.Add(caixa, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # --- vibração
        caixa = wx.StaticBoxSizer(wx.VERTICAL, painel, "Vibração")
        grade = wx.FlexGridSizer(cols=2, vgap=4, hgap=8)
        grade.AddGrowableCol(1)
        self.slider_forte = wx.Slider(caixa.GetStaticBox(), value=255, minValue=0, maxValue=255,
                                      style=wx.SL_HORIZONTAL | wx.SL_VALUE_LABEL)
        self.slider_fraco = wx.Slider(caixa.GetStaticBox(), value=255, minValue=0, maxValue=255,
                                      style=wx.SL_HORIZONTAL | wx.SL_VALUE_LABEL)
        self.spin_duracao = self._spin(caixa.GetStaticBox(), 1.0, 0.1, 10.0, 0.1)
        for rotulo, ctrl in (("Motor forte (esquerdo)", self.slider_forte),
                             ("Motor fraco (direito)", self.slider_fraco),
                             ("Duração (s)", self.spin_duracao)):
            grade.Add(wx.StaticText(caixa.GetStaticBox(), label=rotulo), 0, wx.ALIGN_CENTER_VERTICAL)
            grade.Add(ctrl, 1, wx.EXPAND)
        caixa.Add(grade, 0, wx.EXPAND | wx.ALL, 6)
        linha = wx.BoxSizer(wx.HORIZONTAL)
        bt = wx.Button(caixa.GetStaticBox(), label="Vibrar")
        bt.Bind(wx.EVT_BUTTON, self.on_vibrar)
        linha.Add(bt, 0, wx.RIGHT, 6)
        bt = wx.Button(caixa.GetStaticBox(), label="Parar")
        bt.Bind(wx.EVT_BUTTON, lambda e: self.g.parar_vibracao())
        linha.Add(bt)
        caixa.Add(linha, 0, wx.ALL, 6)
        raiz.Add(caixa, 0, wx.EXPAND | wx.ALL, 10)

        painel.SetSizer(raiz)
        raiz.Fit(self)
        self.SetMinSize(self.GetSize())
        self.Bind(wx.EVT_CLOSE, self.on_fechar)
        self.atualizar_cor_visual()

    @staticmethod
    def _spin(pai, valor, minimo, maximo, passo):
        s = wx.SpinCtrlDouble(pai, value=str(valor), min=minimo, max=maximo, inc=passo,
                              size=pai.FromDIP(wx.Size(70, -1)))
        s.SetDigits(2)
        return s

    # --- ações

    def definir_cor(self, rgb):
        self.rgb = tuple(rgb)
        self.g.luz(self.rgb)
        self.atualizar_cor_visual()

    def on_escolher_cor(self, _):
        dados = wx.ColourData()
        dados.SetColour(wx.Colour(*self.rgb))
        dados.SetChooseFull(True)
        with wx.ColourDialog(self, dados) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                c = dlg.GetColourData().GetColour()
                self.definir_cor((c.Red(), c.Green(), c.Blue()))

    def aplicar_pisca(self):
        if self.chk_piscar.IsChecked():
            self.g.piscar(self.spin_aceso.GetValue(), self.spin_apagado.GetValue())
        else:
            self.g.parar_pisca()

    def on_vibrar(self, _):
        self.g.vibrar(self.slider_forte.GetValue(), self.slider_fraco.GetValue(), self.spin_duracao.GetValue())

    def atualizar_cor_visual(self):
        self.amostra.SetBackgroundColour(wx.Colour(*self.rgb))
        self.amostra.Refresh()
        icone = criar_icone(self.rgb)
        self.SetIcon(icone)
        self.bandeja.SetIcon(icone, TITULO)

    def conexao_mudou(self, conectado, bluetooth):
        """Chamado da thread do controle; só mexe na GUI via wx.CallAfter."""
        if conectado:
            texto = f"Conectado via {'Bluetooth' if bluetooth else 'USB'}"
        else:
            texto = "Controle desconectado. Procurando…"
        wx.CallAfter(self.status.SetLabel, texto)

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
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=PASTA_DADOS / "ds4.log", encoding="utf-8", level=logging.INFO,
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
    janela = Janela(g)
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

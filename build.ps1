# Gera o build de produção com Nuitka: build\faisca\faisca.exe (modo pasta, sem console, um processo).
# Requer: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$py = Join-Path $raiz ".venv\Scripts\python.exe"
$saida = Join-Path $raiz "build"
$icone = Join-Path $saida "icone.ico"

New-Item -ItemType Directory -Force $saida | Out-Null

# ícone do exe: o mesmo círculo da bandeja, em azul
& $py -c @"
import sys, wx
sys.path.insert(0, r'$raiz')
app = wx.App(False)
from app import criar_imagem
assert criar_imagem((0, 90, 255), 64).SaveFile(r'$icone', wx.BITMAP_TYPE_ICO)
"@
if ($LASTEXITCODE -ne 0) { throw "falha ao gerar o ícone" }

& $py -m nuitka `
    --standalone `
    --lto=yes `
    --assume-yes-for-downloads `
    --windows-console-mode=disable `
    --windows-icon-from-ico="$icone" `
    --product-name="Faísca" `
    --file-version=0.1.0 `
    --output-dir="$saida" `
    --output-filename=faisca.exe `
    (Join-Path $raiz "app.py")
if ($LASTEXITCODE -ne 0) { throw "falha no build do Nuitka" }

# o Nuitka gera build\app.dist (ou faisca.dist); entrega como build\faisca
$dist = Get-ChildItem $saida -Directory -Filter "*.dist" | Select-Object -First 1
$final = Join-Path $saida "faisca"
if (Test-Path $final) { Remove-Item $final -Recurse -Force }
Rename-Item $dist.FullName "faisca"

Write-Host "Build pronto: $(Join-Path $saida 'faisca\faisca.exe')"

# Gera o build de produção com Nuitka: build\lumen\lumen.exe (modo pasta, sem console, um processo).
# Requer: <python> -m pip install -r requirements-dev.txt
#
# Uso:
#   .\build.ps1                          # usa o Python do .venv
#   .\build.ps1 -Python python -Pacote   # CI: Python do sistema e gera dist\lumen-<versão>-windows-x64.zip
param(
    [string]$Python = (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"),
    [switch]$Pacote
)
$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$saida = Join-Path $raiz "build"
$icone = Join-Path $raiz "assets\lumen.ico"

# versão única do app (versao.py); o Windows exige 4 números no exe (1.2.3-rc.1 -> 1.2.3.0)
$versao = (& $Python -c "import sys; sys.path.insert(0, r'$raiz'); import versao; print(versao.VERSAO)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $versao) { throw "não consegui ler a versão em versao.py" }
$numerica = ($versao -split "[-+]")[0] + ".0"
Write-Host "Lumen $versao"

New-Item -ItemType Directory -Force $saida | Out-Null

& $Python -m nuitka `
    --standalone `
    --lto=yes `
    --assume-yes-for-downloads `
    --windows-console-mode=disable `
    --windows-icon-from-ico="$icone" `
    --product-name="Lumen" `
    --file-description="Lumen" `
    --product-version=$numerica `
    --file-version=$numerica `
    --output-dir="$saida" `
    --output-filename=lumen.exe `
    (Join-Path $raiz "app.py")
if ($LASTEXITCODE -ne 0) { throw "falha no build do Nuitka" }

# o Nuitka gera build\app.dist; entrega como build\lumen
$dist = Get-ChildItem $saida -Directory -Filter "*.dist" | Select-Object -First 1
$final = Join-Path $saida "lumen"
if (Test-Path $final) { Remove-Item $final -Recurse -Force }
Rename-Item $dist.FullName "lumen"
Write-Host "Build pronto: $(Join-Path $final 'lumen.exe')"

if ($Pacote) {
    $pastaPacotes = Join-Path $raiz "dist"
    New-Item -ItemType Directory -Force $pastaPacotes | Out-Null
    $zip = Join-Path $pastaPacotes "lumen-$versao-windows-x64.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Copy-Item (Join-Path $raiz "LICENSE") $final -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $raiz "README.md") $final
    # o zip contém a pasta "lumen", para não espalhar arquivos ao extrair
    Compress-Archive -Path $final -DestinationPath $zip
    Write-Host "Pacote: $zip"
}

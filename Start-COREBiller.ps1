param([int]$Port=8765)
$ErrorActionPreference='Stop'
$bundlePython=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundlePython) {
    & $bundlePython -X utf8 (Join-Path $PSScriptRoot 'app.py') --port $Port
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 (Join-Path $PSScriptRoot 'app.py') --port $Port
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $PSScriptRoot 'app.py') --port $Port
} else {
    throw 'Se necesita Python 3.10 o posterior. No se requieren paquetes adicionales.'
}

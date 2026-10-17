$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    & .\.venv\Scripts\python.exe -m audience_analysis.app @args
} else {
    & python -m audience_analysis.app @args
}
exit $LASTEXITCODE

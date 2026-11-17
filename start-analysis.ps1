<#!
.SYNOPSIS
Pornește automat pipeline-ul CLI pentru o imagine sau un videoclip local.

.EXAMPLE
.\start-analysis.ps1 -InputPath "C:\Users\Nume\Videos\clip.mp4"
.EXAMPLE
.\start-analysis.ps1
#>
param(
    [string]$InputPath,
    [ValidateSet("auto", "image", "video")]
    [string]$Mode = "auto",
    [ValidateRange(0.01, 3600)]
    [double]$SampleInterval = 1.0,
    [ValidateSet("auto", "cpu", "cuda")]
    [string]$Device = "auto",
    [string]$OutputDir,
    [string]$PythonPath,
    [switch]$AllowModelDownload
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $PSScriptRoot ".venv-completion\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        $PythonPath = Join-Path $PSScriptRoot ".venv-local\Scripts\python.exe"
    }
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        $PythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    }
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python local indisponibil. Indică -PythonPath sau pregătește mediul din docs/environment.md."
}
$analysisPython = (Resolve-Path -LiteralPath $PythonPath).Path

if ([string]::IsNullOrWhiteSpace($InputPath)) {
    $InputPath = Read-Host "Calea către imagine sau videoclip"
}
if ([string]::IsNullOrWhiteSpace($InputPath)) {
    throw "Nu a fost oferit niciun fișier."
}

$source = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
if ($Mode -eq "auto") {
    $imageExtensions = ".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"
    $extension = [System.IO.Path]::GetExtension($source.Path).ToLowerInvariant()
    $Mode = if ($imageExtensions -contains $extension) { "image" } else { "video" }
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot ("results\analysis-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}

Write-Host "Pornesc analiza $Mode pentru: $source" -ForegroundColor Magenta
Write-Host "Rapoarte: $OutputDir" -ForegroundColor Magenta
$analysisArguments = @('-X', 'utf8', '-m', 'audience_analysis', $Mode, '--input', $source.Path, '--output-dir', $OutputDir, '--sample-interval', $SampleInterval, '--device', $Device)
if ($AllowModelDownload) { $analysisArguments += '--allow-model-download' }
& $analysisPython @analysisArguments
exit $LASTEXITCODE

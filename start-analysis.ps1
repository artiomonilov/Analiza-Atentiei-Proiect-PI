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
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Nu există .venv\Scripts\python.exe. Creează mediul și instalează dependențele din README."
}

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
& $python -m audience_analysis $Mode --input $source.Path --output-dir $OutputDir --sample-interval $SampleInterval --device $Device
exit $LASTEXITCODE

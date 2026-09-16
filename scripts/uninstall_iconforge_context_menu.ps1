Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$extensions = @(
    ".ico",
    ".png",
    ".svg",
    ".gif",
    ".bmp",
    ".jpg",
    ".jpeg",
    ".webp"
)

foreach ($ext in $extensions) {
    $key = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\BossForgeOpenInIconForge"
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force
    }
}

Write-Host "Open in IconForge context menu removed."

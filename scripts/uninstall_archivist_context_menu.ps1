Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$keys = @(
    "HKCU:\Software\Classes\Directory\shell\BossForgeSummonArchivist",
    "HKCU:\Software\Classes\*\shell\BossForgeSummonArchivist",
    "HKCU:\Software\Classes\Directory\Background\shell\BossForgeSummonArchivist"
)

foreach ($key in $keys) {
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force
    }
}

Write-Host "Summon Archivist context menu removed."

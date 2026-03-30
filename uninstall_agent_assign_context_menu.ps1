Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$keys = @(
    "HKCU:\Software\Classes\Directory\shell\BossForgeAssignAgent",
    "HKCU:\Software\Classes\*\shell\BossForgeAssignAgent",
    "HKCU:\Software\Classes\Directory\Background\shell\BossForgeAssignAgent"
)

foreach ($key in $keys) {
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force
    }
}

Write-Host "Assign Agent context menu removed."

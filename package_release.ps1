param(
    [string]$Version = "0.1.0",
    [string]$ExeName = "BossForgeLauncher.exe",
    [switch]$RebuildExe,
    [switch]$NoShortcut
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$distExe = Join-Path $root ("dist\" + $ExeName)
if ($RebuildExe -or !(Test-Path $distExe)) {
    Write-Host "Building launcher EXE first..."
    powershell -ExecutionPolicy Bypass -File (Join-Path $root "build_launcher_exe.ps1") -Clean
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build launcher executable."
    }
}

if (!(Test-Path $distExe)) {
    throw "Expected executable not found: $distExe"
}

$releaseDir = Join-Path $root ("releases\v" + $Version)
if (!(Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

$versionedExe = "BossForgeLauncher-v$Version.exe"
$targetExePath = Join-Path $releaseDir $versionedExe
Copy-Item -Path $distExe -Destination $targetExePath -Force

$manifest = [ordered]@{
    name = "BossForgeLauncher"
    version = $Version
    builtAt = (Get-Date).ToString("o")
    sourceExe = $distExe
    packagedExe = $targetExePath
}

$manifestPath = Join-Path $releaseDir "release_manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Out-File $manifestPath -Encoding utf8

if (-not $NoShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "BossForge Launcher.lnk"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetExePath
    $shortcut.WorkingDirectory = $releaseDir
    $shortcut.Description = "BossForgeOS Unified Launcher"
    $shortcut.Save()
}

Write-Host "Release packaged: $targetExePath"
Write-Host "Manifest: $manifestPath"

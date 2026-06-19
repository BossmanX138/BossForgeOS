param(
    [string]$Version = "0.1.0",
    [string]$ExeName = "BossForgeLauncher.exe",
    [string]$BuildId = "",
    [switch]$RebuildExe,
    [switch]$NoShortcut,
    [switch]$SkipLatest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
Set-Location $projectRoot

if ([string]::IsNullOrWhiteSpace($BuildId)) {
    $BuildId = Get-Date -Format "yyyyMMdd-HHmmss"
}

$distExe = Join-Path $projectRoot ("dist\" + $ExeName)
if ($RebuildExe -or !(Test-Path $distExe)) {
    Write-Host "Building launcher EXE first..."
    powershell -ExecutionPolicy Bypass -File (Join-Path $scriptRoot "build_launcher_exe.ps1") -Clean
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build launcher executable."
    }
}

if (!(Test-Path $distExe)) {
    throw "Expected executable not found: $distExe"
}

$releaseDir = Join-Path $projectRoot ("releases\v" + $Version)
if (!(Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

$versionedExe = "BossForgeLauncher-v$Version-$BuildId.exe"
$targetExePath = Join-Path $releaseDir $versionedExe
Copy-Item -Path $distExe -Destination $targetExePath -Force

$sha256 = (Get-FileHash -Algorithm SHA256 -Path $targetExePath).Hash
$gitCommit = ""
try {
    $gitCommit = (git -C $projectRoot rev-parse --short HEAD).Trim()
} catch {
    $gitCommit = ""
}

$manifest = [ordered]@{
    name = "BossForgeLauncher"
    version = $Version
    buildId = $BuildId
    builtAt = (Get-Date).ToString("o")
    sourceCommit = $gitCommit
    sha256 = $sha256
    sourceExe = $distExe
    packagedExe = $targetExePath
}

$manifestPath = Join-Path $releaseDir "release_manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Out-File $manifestPath -Encoding utf8

if (-not $SkipLatest) {
    $latestDir = Join-Path $projectRoot "releases\latest"
    if (!(Test-Path $latestDir)) {
        New-Item -ItemType Directory -Path $latestDir | Out-Null
    }

    $latestExePath = Join-Path $latestDir "BossForgeLauncher-latest.exe"
    $latestManifestPath = Join-Path $latestDir "release_manifest.json"
    Copy-Item -Path $targetExePath -Destination $latestExePath -Force

    $latestManifest = [ordered]@{
        latest = $true
        version = $Version
        buildId = $BuildId
        builtAt = $manifest.builtAt
        sourceCommit = $gitCommit
        sha256 = $sha256
        artifact = $latestExePath
        canonicalArtifact = $targetExePath
    }
    $latestManifest | ConvertTo-Json -Depth 4 | Out-File $latestManifestPath -Encoding utf8
}

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
if (-not $SkipLatest) {
    Write-Host "Latest alias: $(Join-Path $projectRoot 'releases\latest\BossForgeLauncher-latest.exe')"
}

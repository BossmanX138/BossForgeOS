[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$BuildId = "",
    [string]$SourceCommit = "",
    [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"

function Get-DefaultVersion {
    $latestManifest = Join-Path $PSScriptRoot "..\releases\latest\release_manifest.json"
    if (-not (Test-Path $latestManifest)) {
        return "0.1.3"
    }
    $manifest = Get-Content $latestManifest -Raw | ConvertFrom-Json
    if (-not $manifest.version) {
        return "0.1.3"
    }
    $parts = "$($manifest.version)".Split(".")
    if ($parts.Length -ne 3) {
        return "0.1.3"
    }
    $patch = [int]$parts[2] + 1
    return "$($parts[0]).$($parts[1]).$patch"
}

function Ensure-Dir([string]$PathValue) {
    if (-not (Test-Path $PathValue)) {
        New-Item -ItemType Directory -Path $PathValue | Out-Null
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$resolvedVersion = if ($Version) { $Version } else { Get-DefaultVersion }
$resolvedBuildId = if ($BuildId) { $BuildId } else { Get-Date -Format "yyyyMMdd-HHmmss" }
$resolvedCommit = if ($SourceCommit) { $SourceCommit } else { (git rev-parse --short HEAD).Trim() }

$installerPayloadDir = Join-Path $projectRoot "installer\payload"
$distDir = Join-Path $projectRoot "dist"
$releasesDir = Join-Path $projectRoot "releases"
$latestDir = Join-Path $releasesDir "latest"
$versionDir = Join-Path $releasesDir ("v" + $resolvedVersion)
$archiveDir = Join-Path $releasesDir ("archive\launcher-era\" + $resolvedBuildId)

if ((Test-Path $installerPayloadDir)) { Remove-Item -Recurse -Force $installerPayloadDir }
if ((Test-Path $distDir)) { Remove-Item -Recurse -Force $distDir }
Ensure-Dir $installerPayloadDir
Ensure-Dir $latestDir
Ensure-Dir $versionDir

Write-Host "Building BossForgeOS.exe..."
python -m PyInstaller installer\BossForgeOS.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "BossForgeOS.exe build failed." }

Write-Host "Creating installer payload..."
python installer\build_release_payload.py `
    --project-root $projectRoot `
    --launcher-exe (Join-Path $distDir "BossForgeOS.exe") `
    --output-dir $installerPayloadDir `
    --version $resolvedVersion `
    --build-id $resolvedBuildId `
    --source-commit $resolvedCommit
if ($LASTEXITCODE -ne 0) { throw "Payload build failed." }

Write-Host "Building Install BossForge_OS.exe..."
python -m PyInstaller installer\Install_BossForge_OS.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "Installer build failed." }

if (-not $SkipArchive) {
    $legacyArtifacts = Get-ChildItem $releasesDir -Recurse -File -Filter "BossForgeLauncher*.exe" -ErrorAction SilentlyContinue
    if ($legacyArtifacts) {
        Ensure-Dir $archiveDir
        foreach ($artifact in $legacyArtifacts) {
            $destination = Join-Path $archiveDir $artifact.Name
            Move-Item -LiteralPath $artifact.FullName -Destination $destination -Force
        }
    }
}

$installerExe = Join-Path $distDir "Install BossForge_OS.exe"
$latestInstaller = Join-Path $latestDir "Install BossForge_OS.exe"
$versionInstaller = Join-Path $versionDir ("Install BossForge_OS-" + $resolvedVersion + "-" + $resolvedBuildId + ".exe")
$releaseManifestPath = Join-Path $installerPayloadDir "release_manifest.json"

Copy-Item -LiteralPath $installerExe -Destination $latestInstaller -Force
Copy-Item -LiteralPath $installerExe -Destination $versionInstaller -Force

$manifest = Get-Content $releaseManifestPath -Raw | ConvertFrom-Json
if ($manifest.PSObject.Properties.Name -contains "artifact") {
    $manifest.artifact = $latestInstaller
} else {
    $manifest | Add-Member -NotePropertyName artifact -NotePropertyValue $latestInstaller
}
if ($manifest.PSObject.Properties.Name -contains "canonicalArtifact") {
    $manifest.canonicalArtifact = $versionInstaller
} else {
    $manifest | Add-Member -NotePropertyName canonicalArtifact -NotePropertyValue $versionInstaller
}
if ($manifest.PSObject.Properties.Name -contains "latest") {
    $manifest.latest = $true
} else {
    $manifest | Add-Member -NotePropertyName latest -NotePropertyValue $true
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $latestDir "release_manifest.json")
$manifest.latest = $false
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $versionDir "release_manifest.json")

Write-Host "Built installer: $latestInstaller"
Write-Host "Versioned installer: $versionInstaller"

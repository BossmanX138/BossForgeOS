param(
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[bforge-cli] $Message"
}

$RepoRoot = (Resolve-Path -Path $RepoRoot).Path
$CoreEntry = Join-Path $RepoRoot "core\bforge.py"
if (-not (Test-Path $CoreEntry)) {
    throw "core\\bforge.py not found under repo root: $RepoRoot"
}

$UserBin = Join-Path $HOME "BossCrafts\bin"
New-Item -ItemType Directory -Path $UserBin -Force | Out-Null

$RepoPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RepoRootPosix = $RepoRoot.Replace('\\', '/')
$RepoPythonPosix = $RepoPython.Replace('\\', '/')
$CmdShim = Join-Path $UserBin "bforge.cmd"
$PsShim = Join-Path $UserBin "bforge.ps1"
$ShShim = Join-Path $UserBin "bforge"

$cmdContent = @"
@echo off
setlocal
set "BOSSFORGE_ROOT=$RepoRoot"
set "PYTHONPATH=$RepoRoot;%PYTHONPATH%"
if exist "$RepoPython" (
  "$RepoPython" -m core.bforge %*
) else (
  python -m core.bforge %*
)
"@

$psContent = @"
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$Args
)
`$env:BOSSFORGE_ROOT = "$RepoRoot"
if ([string]::IsNullOrWhiteSpace(`$env:PYTHONPATH)) {
    `$env:PYTHONPATH = "$RepoRoot"
} else {
    `$env:PYTHONPATH = "$RepoRoot;`$env:PYTHONPATH"
}
if (Test-Path "$RepoPython") {
    & "$RepoPython" -m core.bforge @Args
} else {
    & python -m core.bforge @Args
}
"@

$shTemplate = @'
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="__REPO_ROOT__"
export BOSSFORGE_ROOT="__REPO_ROOT__"
if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="__REPO_ROOT__:${PYTHONPATH}"
else
    export PYTHONPATH="__REPO_ROOT__"
fi
if [ -x "__REPO_PYTHON__" ]; then
    "__REPO_PYTHON__" -m core.bforge "$@"
else
  python -m core.bforge "$@"
fi
'@

$shContent = $shTemplate.Replace("__REPO_ROOT__", $RepoRootPosix).Replace("__REPO_PYTHON__", $RepoPythonPosix)

Set-Content -Path $CmdShim -Value $cmdContent -Encoding ASCII
Set-Content -Path $PsShim -Value $psContent -Encoding ASCII
Set-Content -Path $ShShim -Value $shContent -Encoding ASCII

$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$NeedUpdate = $true
if ($CurrentPath) {
    $segments = $CurrentPath.Split(';') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($segment in $segments) {
        if ($segment.TrimEnd('\\') -ieq $UserBin.TrimEnd('\\')) {
            $NeedUpdate = $false
            break
        }
    }
}

if ($NeedUpdate) {
    $NewPath = if ([string]::IsNullOrWhiteSpace($CurrentPath)) { $UserBin } else { "$CurrentPath;$UserBin" }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Step "Added $UserBin to user PATH"
} else {
    Write-Step "User PATH already includes $UserBin"
}

Write-Step "Installed shims:"
Write-Step "  $CmdShim"
Write-Step "  $PsShim"
Write-Step "  $ShShim"
Write-Step "Open a new terminal, then run: bforge status"

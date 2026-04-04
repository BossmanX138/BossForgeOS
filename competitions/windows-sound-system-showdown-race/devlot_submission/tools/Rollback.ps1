$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$manager = Join-Path $scriptRoot "SystemSoundManager.ps1"

if (-not (Test-Path $manager)) {
    throw "SystemSoundManager.ps1 not found at $manager"
}

& $manager -Action rollback

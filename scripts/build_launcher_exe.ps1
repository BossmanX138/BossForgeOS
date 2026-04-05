param(
    [string]$PythonExe = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $PythonExe = "python"
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

if ($Clean) {
    if (Test-Path "$root\build") { Remove-Item "$root\build" -Recurse -Force }
    if (Test-Path "$root\dist") { Remove-Item "$root\dist" -Recurse -Force }
    if (Test-Path "$root\BossForgeLauncher.spec") { Remove-Item "$root\BossForgeLauncher.spec" -Force }
}

Invoke-Step -Command $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Step -Command $PythonExe -Arguments @("-m", "pip", "install", "pyinstaller")


# Resolve absolute path to bossforge_launcher.py
$launcherPath = Join-Path $root "..\launcher\bossforge_launcher.py" | Resolve-Path -ErrorAction Stop
Invoke-Step -Command $PythonExe -Arguments @("-m", "PyInstaller", "--onefile", "--name", "BossForgeLauncher", $launcherPath)

$exePath = Join-Path $root "dist\BossForgeLauncher.exe"
if (!(Test-Path $exePath)) {
    throw "Build finished without expected output: $exePath"
}

Write-Host "Launcher EXE built at: $exePath"

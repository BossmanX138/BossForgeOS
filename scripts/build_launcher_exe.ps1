param(
    [string]$PythonExe = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
Set-Location $projectRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
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
    if (Test-Path "$projectRoot\build") { Remove-Item "$projectRoot\build" -Recurse -Force }
    if (Test-Path "$projectRoot\dist") { Remove-Item "$projectRoot\dist" -Recurse -Force }
    if (Test-Path "$projectRoot\BossForgeLauncher.spec") { Remove-Item "$projectRoot\BossForgeLauncher.spec" -Force }
}

Invoke-Step -Command $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Step -Command $PythonExe -Arguments @("-m", "pip", "install", "pyinstaller")


# Resolve absolute path to bossforge_launcher.py
$launcherPath = Join-Path $projectRoot "launcher\bossforge_launcher.py" | Resolve-Path -ErrorAction Stop
Invoke-Step -Command $PythonExe -Arguments @(
    "-m", "PyInstaller",
    "--onefile",
    "--name", "BossForgeLauncher",
    "--distpath", (Join-Path $projectRoot "dist"),
    "--workpath", (Join-Path $projectRoot "build"),
    "--specpath", $projectRoot,
    $launcherPath
)

$exePath = Join-Path $projectRoot "dist\BossForgeLauncher.exe"
if (!(Test-Path $exePath)) {
    throw "Build finished without expected output: $exePath"
}

Write-Host "Launcher EXE built at: $exePath"

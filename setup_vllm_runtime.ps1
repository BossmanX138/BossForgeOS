param(
    [string]$RuntimeRoot = ".runtime/vllm_runtime",
    [string]$BasePython = "",
    [string]$TorchVersion = "2.10.0",
    [string]$VllmVersion = "0.8.3"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[vllm-runtime] $Message"
}

function Invoke-Checked([string]$Label, [string]$Exe, [string[]]$Args) {
    Write-Step $Label
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Resolve-BasePython([string]$RequestedBasePython) {
    if ($RequestedBasePython -and (Test-Path $RequestedBasePython)) {
        return $RequestedBasePython
    }

    $candidates = @(
        "C:\\Users\\$env:USERNAME\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
        "C:\\Program Files\\Python312\\python.exe",
        "C:\\Program Files (x86)\\Python312\\python.exe",
        "C:\\Users\\$env:USERNAME\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
        "C:\\Program Files\\Python311\\python.exe",
        ".venv/Scripts/python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return ""
}

function Get-PythonVersion([string]$PythonExe) {
    $versionOutput = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect Python version from $PythonExe"
    }
    return ($versionOutput | Select-Object -First 1).Trim()
}

$runtimePath = Resolve-Path -Path "." | ForEach-Object { Join-Path $_.Path $RuntimeRoot }
$runtimePython = Join-Path $runtimePath "Scripts/python.exe"
$resolvedBasePython = Resolve-BasePython -RequestedBasePython $BasePython

if (-not $resolvedBasePython) {
    throw "No compatible base Python found. Install Python 3.12 or pass -BasePython explicitly."
}

$pythonVersion = Get-PythonVersion -PythonExe $resolvedBasePython
Write-Step "Base Python: $resolvedBasePython (version $pythonVersion)"

if ($pythonVersion -notin @("3.11", "3.12")) {
    throw "Unsupported base Python version $pythonVersion. Use Python 3.11 or 3.12 for vLLM runtime setup."
}

if (-not (Test-Path $runtimePython)) {
    Write-Step "Creating runtime venv at $runtimePath"
    & $resolvedBasePython -m venv $runtimePath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create runtime venv using $resolvedBasePython"
    }
}

if (-not (Test-Path $runtimePython)) {
    throw "Failed to create runtime Python at: $runtimePython"
}

Invoke-Checked -Label "Upgrading pip/setuptools/wheel/build tooling" -Exe $runtimePython -Args @(
    "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "packaging", "setuptools-scm", "numpy"
)

Invoke-Checked -Label "Installing torch==$TorchVersion" -Exe $runtimePython -Args @(
    "-m", "pip", "install", "torch==$TorchVersion"
)

Invoke-Checked -Label "Installing vllm==$VllmVersion (no-build-isolation)" -Exe $runtimePython -Args @(
    "-m", "pip", "install", "vllm==$VllmVersion", "--no-build-isolation"
)

Invoke-Checked -Label "Verifying runtime imports" -Exe $runtimePython -Args @(
    "-c",
    "import importlib.util, sys, torch, vllm; print('torch', torch.__version__); spec = importlib.util.find_spec('vllm._C'); sys.exit(0 if spec else 17)"
)

Write-Step "Runtime ready: $runtimePython"
Write-Step "You can now launch with start_bossforge_internal_vllm.cmd"

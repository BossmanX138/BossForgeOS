Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "assign_agent_context.cmd"

if (!(Test-Path $runner)) {
    throw "Missing runner script: $runner"
}

$agentMap = @{
    "Archivist" = "archivist"
    "CodeMage" = "codemage"
    "Runeforge" = "runeforge"
    "Devlot" = "devlot"
    "Model Gateway" = "model_gateway"
}

function Set-AssignCascade {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseKey,
        [Parameter(Mandatory = $true)]
        [string]$TargetArg
    )

    $parentKey = Join-Path $BaseKey "shell\BossForgeAssignAgent"
    New-Item -Path $parentKey -Force | Out-Null
    Set-ItemProperty -Path $parentKey -Name "MUIVerb" -Value "Assign Agent"
    Set-ItemProperty -Path $parentKey -Name "SubCommands" -Value ""
    Set-ItemProperty -Path $parentKey -Name "Icon" -Value "imageres.dll,-5352"

    foreach ($label in $agentMap.Keys) {
        $slug = ($label -replace "\s+", "")
        $agent = $agentMap[$label]
        $childShell = Join-Path $parentKey ("shell\" + $slug)
        $childCmd = Join-Path $childShell "command"

        New-Item -Path $childShell -Force | Out-Null
        New-Item -Path $childCmd -Force | Out-Null

        Set-ItemProperty -Path $childShell -Name "MUIVerb" -Value $label

        $cmd = "cmd.exe /c `"`"$runner`" $agent $TargetArg`""
        Set-ItemProperty -Path $childCmd -Name "(default)" -Value $cmd
    }
}

Set-AssignCascade -BaseKey "HKCU:\Software\Classes\Directory" -TargetArg '"%1"'
Set-AssignCascade -BaseKey "HKCU:\Software\Classes\*" -TargetArg '"%1"'
Set-AssignCascade -BaseKey "HKCU:\Software\Classes\Directory\Background" -TargetArg '"%V"'

Write-Host "Assign Agent context menu installed."

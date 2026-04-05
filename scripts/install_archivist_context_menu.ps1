Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "summon_archivist.cmd"

if (!(Test-Path $runner)) {
    throw "Missing runner script: $runner"
}

function Set-MenuEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseKey,
        [Parameter(Mandatory = $true)]
        [string]$CommandArg
    )

    $shellKey = Join-Path $BaseKey "shell\BossForgeSummonArchivist"
    $cmdKey = Join-Path $shellKey "command"

    New-Item -Path $shellKey -Force | Out-Null
    New-Item -Path $cmdKey -Force | Out-Null

    Set-ItemProperty -Path $shellKey -Name "MUIVerb" -Value "Summon Archivist"
    Set-ItemProperty -Path $shellKey -Name "Icon" -Value "imageres.dll,-102"

    $cmd = "cmd.exe /c `"`"$runner`" $CommandArg`""
    Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $cmd
}

Set-MenuEntry -BaseKey "HKCU:\Software\Classes\Directory" -CommandArg '"%1" --init-repo'
Set-MenuEntry -BaseKey "HKCU:\Software\Classes\*" -CommandArg '"%1"'
Set-MenuEntry -BaseKey "HKCU:\Software\Classes\Directory\Background" -CommandArg '"%V"'

Write-Host "Summon Archivist context menu installed."

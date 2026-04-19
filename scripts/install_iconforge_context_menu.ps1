Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "open_in_iconforge_context.cmd"

if (!(Test-Path $runner)) {
    throw "Missing runner script: $runner"
}

$extensions = @(
    ".ico",
    ".png",
    ".svg",
    ".gif",
    ".bmp",
    ".jpg",
    ".jpeg",
    ".webp"
)

function Set-IconForgeEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Extension
    )

    $baseKey = "HKCU:\Software\Classes\SystemFileAssociations\$Extension"
    $shellKey = Join-Path $baseKey "shell\BossForgeOpenInIconForge"
    $cmdKey = Join-Path $shellKey "command"

    New-Item -Path $shellKey -Force | Out-Null
    New-Item -Path $cmdKey -Force | Out-Null

    Set-ItemProperty -Path $shellKey -Name "MUIVerb" -Value "Open in IconForge"
    Set-ItemProperty -Path $shellKey -Name "Icon" -Value "imageres.dll,-5302"

    $cmd = "cmd.exe /c `"`"$runner`" `"`"%1`"`"`""
    Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $cmd
}

foreach ($ext in $extensions) {
    Set-IconForgeEntry -Extension $ext
}

Write-Host "Open in IconForge context menu installed for: $($extensions -join ', ')"

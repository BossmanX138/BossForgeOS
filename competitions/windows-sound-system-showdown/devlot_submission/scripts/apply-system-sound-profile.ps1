param(
    [Parameter(Mandatory=$true)]
    [string]$ProfileFolder
)

if (-not (Test-Path $ProfileFolder)) {
    throw "Profile folder does not exist: $ProfileFolder"
}

$map = @{
    "OpenApp.wav" = "Open"
    "CloseApp.wav" = "Close"
    "Notification.wav" = ".Default"
    "Info.wav" = "SystemAsterisk"
    "Warning.wav" = "SystemExclamation"
    "Error.wav" = "SystemHand"
    "Mail.wav" = "MailBeep"
    "Reminder.wav" = "Notification.Reminder"
}

foreach ($entry in $map.GetEnumerator()) {
    $file = Join-Path $ProfileFolder $entry.Key
    if (Test-Path $file) {
        $key = "HKCU:\AppEvents\Schemes\Apps\.Default\$($entry.Value)\.Current"
        if (-not (Test-Path $key)) {
            New-Item -Path $key -Force | Out-Null
        }
        Set-ItemProperty -Path $key -Name "(default)" -Value $file
        Write-Host "Mapped $($entry.Value) -> $file"
    }
}

Write-Host "System sound profile application complete."

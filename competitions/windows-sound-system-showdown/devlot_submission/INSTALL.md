# Install and Run

## Prerequisites
- Windows 10/11
- .NET 8 SDK

## 1) Build and run user-mode prototype
```powershell
cd src/BossForge.SoundSystem
dotnet restore
dotnet run
```

If no .NET SDK is installed, install from:
- https://aka.ms/dotnet/download

## 2) Prepare optional system sound profile
Create a folder with files named exactly:
- OpenApp.wav
- CloseApp.wav
- Notification.wav
- Info.wav
- Warning.wav
- Error.wav
- Mail.wav
- Reminder.wav

Template location:
- `assets/system-sound-profile-template`

## 3) Safe replacement flow
Option A: inside app
1. Run option `7` to back up current system sounds.
2. Run option `8` and provide your profile folder path.
3. Run option `9` to restore.

Option B: PowerShell scripts
```powershell
./scripts/backup-system-sounds.ps1
./scripts/apply-system-sound-profile.ps1 -ProfileFolder "C:\path\to\profile"
./scripts/restore-system-sounds.ps1
```

## 4) Privileged APO/driver lane (later, elevated)
See:
- `stubs/apo-driver/README.md`
- `stubs/apo-driver/INSTALL_APO.md`

These steps require admin rights, signing, and are intentionally separated from sandbox-safe operations.

## Rollback checklist
- Stop interception in app (option `4`).
- Restore system sounds (option `9` or script).
- For APO experiments: execute rollback commands in `stubs/apo-driver/INSTALL_APO.md`.

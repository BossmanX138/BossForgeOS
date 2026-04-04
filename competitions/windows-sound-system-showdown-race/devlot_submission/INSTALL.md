# Install and Build

## Prerequisites

- Windows 10/11
- CMake 3.20+
- MSVC (Visual Studio 2022 Build Tools or full IDE)
- PowerShell 7+ (or Windows PowerShell 5.1)

## Build Demo App

From submission root:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022"
cmake --build build --config Release
```

Binary output:

- `build/Release/BossForgeSoundDemo.exe`

## Run Demo

```powershell
./build/Release/BossForgeSoundDemo.exe
```

## System Sound Manager Setup

1. Edit `tools/system-sounds-manifest.json` and point each event to real `.wav` files.
2. Run install action:

```powershell
./tools/SystemSoundManager.ps1 -Action install
```

3. Check current status:

```powershell
./tools/SystemSoundManager.ps1 -Action status
```

4. Roll back to previous state:

```powershell
./tools/SystemSoundManager.ps1 -Action rollback
```

Or use shortcut:

```powershell
./tools/Rollback.ps1
```

## Sandbox Note

APO registration and endpoint binding are represented as implementation stubs and architecture plan due to sandbox constraints. User-mode DSP and safety tooling are fully included.

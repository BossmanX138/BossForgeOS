# INSTALL - BossForge Sound System Prototype

## Prerequisites
- Windows 10/11
- CMake 3.20+
- Visual Studio 2022 Build Tools (MSVC) or equivalent C++17 compiler

## Build Steps (PowerShell)
1. `cd d:/Bosscrafts/BossForgeOS/competitions/windows-sound-system-showdown-race/bossforge_unified_candidate`
2. `cmake -S . -B build -G "Visual Studio 17 2022"`
3. `cmake --build build --config Release`

## Run
- `./build/Release/BossForgeSoundShowdown.exe`

## Integrated System Sound Tooling (PowerShell)

1. Edit `tools/system-sounds-manifest.json` to point events to valid `.wav` paths.
2. Run install action:
	- `powershell -ExecutionPolicy Bypass -File .\tools\SystemSoundManager.ps1 -Action install`
3. Check status:
	- `powershell -ExecutionPolicy Bypass -File .\tools\SystemSoundManager.ps1 -Action status`
4. Rollback:
	- `powershell -ExecutionPolicy Bypass -File .\tools\Rollback.ps1`

## Notes
- The APO component is represented as an integration stub in `stubs/apo-driver/`.
- Runtime demo assets are generated under `runtime/` at execution.
- If you need a clean reset, delete `runtime/` and rerun.

# INSTALL - BossForge Sound System Prototype

## Prerequisites
- Windows 10/11
- CMake 3.20+
- Visual Studio 2022 Build Tools (MSVC) or equivalent C++17 compiler

## Build Steps (PowerShell)
1. `cd d:/Bosscrafts/BossForgeOS/competitions/windows-sound-system-showdown-race/codemage_submission`
2. `cmake -S . -B build -G "Visual Studio 17 2022"`
3. `cmake --build build --config Release`

## Run
- `./build/Release/BossForgeSoundShowdown.exe`

## Notes
- The APO component is represented as an integration stub in `stubs/apo-driver/`.
- Runtime demo assets are generated under `runtime/` at execution.
- If you need a clean reset, delete `runtime/` and rerun.

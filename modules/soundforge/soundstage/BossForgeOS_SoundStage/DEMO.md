# DEMO - SoundStage Walkthrough

## Goal
Demonstrate all required SoundStage features in one execution flow, integrated with BossForgeOS.

## Steps
1. Build and run executable from [INSTALL.md](INSTALL.md)
2. Observe APO/interception banner on startup
3. Observe output-device list print, then runtime switch to headset profile
4. Observe intercepted frame count and upmixed frame count
5. Observe system sound replacement results for `open_app` and `close_app`
6. Observe restore-defaults message showing backup path
7. Run PowerShell status command for registry-backed event-sound view:
   - `powershell -ExecutionPolicy Bypass -File .\tools\SystemSoundManager.ps1 -Action status`

## Expected Console Signals
- `APO Stub: BossForge APO Stub [LFX/GFX Pre-Speaker Interceptor]`
- `Intercepted frames: <n>`
- `Upmixed frame count: <n>`
- `System sound swap open_app: ok`
- `System sound swap close_app: ok`
- `Restored defaults from: .../runtime/sound_backups`

## Feature-to-Requirement Mapping
- Pre-speaker interception: `PreSpeakerInterceptor`, APO stub, architecture plan
- 10-band EQ: `TenBandEqualizer`
- Speaker selection and switching: `SpeakerSelector`, `ConsoleControlPanel`
- Stereo upmix to 7.2: `StereoTo72Upmixer`
- System sound replacement manager: `SystemSoundReplacementManager`
- Rollback/safety: `RollbackSafetyManager`, backup/restore behavior

## Unified Additions
- PowerShell manager offers direct registry orchestration for system event sounds with backup/rollback workflows in `tools/`

## Cross-References
- [README.md](README.md): SoundStage overview
- [README-soundstage-daemon.md](README-soundstage-daemon.md): Daemon usage and API
- [ARCHITECTURE.md](ARCHITECTURE.md): SoundStage architecture
- [INSTALL.md](INSTALL.md): Build and install

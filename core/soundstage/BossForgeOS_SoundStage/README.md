# BossForgeOS SoundStage

SoundStage is the deterministic sound event engine for BossForgeOS, providing true program open/close sounds, per-app/event mapping, system sound replacement, rollback, diagnostics, and bundle import/export. It is fully integrated with the BossForgeOS daemon, Control Hall GUI, and VS Code extension.

## Table of Contents

- [What Is Implemented](#what-is-implemented)
- [Folder Layout](#folder-layout)
- [Integration & Usage](#integration-usage)
- [Quick Start](#quick-start)
- [Cross-References](#cross-references)

## What Is Implemented
- Pre-speaker interception model via `PreSpeakerInterceptor` + APO integration stub (`stubs/apo-driver`)
- 10-band equalizer interface and DSP processor (`TenBandEqualizer`)
- Output device selection and runtime switching (`SpeakerSelector`)
- Stereo-to-7.2 routing engine (`StereoTo72Upmixer`) with explicit 9-channel mapping (7 bed + dual LFE)
- System sound replacement manager with backup/restore transaction behavior (`SystemSoundReplacementManager`)
- Rollback safety layer with undo stack for fault recovery (`RollbackSafetyManager`)
- Runnable console demo wiring all modules (`src/main.cpp`)
- Integrated PowerShell registry-based system-sound manager with backup/status/rollback commands (`tools/`)

## Folder Layout
- `src/`: prototype source code modules
- `stubs/apo-driver/`: APO-driver-facing integration stubs
- `configs/`: default profile and tuning values
- `runtime/`: generated at runtime for demo wav files and backups
- `tools/`: system-sound manager scripts and manifest

## Integration & Usage
- SoundStage is managed by the BossForgeOS daemon and exposes a local HTTP API for integration and control
- Fully integrated with Control Hall GUI (sound scheme management, diagnostics, analytics)
- Accessible via VS Code extension (event streaming, import/export, analytics)

## Quick Start
See [INSTALL.md](INSTALL.md) then [DEMO.md](DEMO.md).

## Cross-References
- [README-soundstage-daemon.md](README-soundstage-daemon.md): Daemon usage and API
- [ARCHITECTURE.md](ARCHITECTURE.md): SoundStage architecture
- [INSTALL.md](INSTALL.md): Build and install
- [DEMO.md](DEMO.md): Feature demonstration

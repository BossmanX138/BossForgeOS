# BossForge Sound System - Unified Candidate

This is the merged BossForgeOS adoption candidate.

- Runtime core baseline: CodeMage submission
- System-sound ops tooling: Devlot PowerShell manager (`tools/SystemSoundManager.ps1`, `tools/Rollback.ps1`)

The package combines pre-speaker interception architecture with user-mode runnable modules for EQ, output switching, stereo-to-7.2 upmix routing, and system sound replacement with rollback safety.

## Table of Contents

- [What Is Implemented](#what-is-implemented)
- [Folder Layout](#folder-layout)
- [Adoption Position](#adoption-position)
- [Quick Start](#quick-start)

## What Is Implemented
- Pre-speaker interception model via `PreSpeakerInterceptor` + APO integration stub (`stubs/apo-driver`).
- 10-band equalizer interface and DSP processor (`TenBandEqualizer`).
- Output device selection and runtime switching (`SpeakerSelector`).
- Stereo-to-7.2 routing engine (`StereoTo72Upmixer`) with explicit 9-channel mapping (7 bed + dual LFE).
- System sound replacement manager with backup/restore transaction behavior (`SystemSoundReplacementManager`).
- Rollback safety layer with undo stack for fault recovery (`RollbackSafetyManager`).
- Runnable console demo wiring all modules (`src/main.cpp`).
- Integrated PowerShell registry-based system-sound manager with backup/status/rollback commands (`tools/`).

## Folder Layout
- `src/` - prototype source code modules
- `stubs/apo-driver/` - APO-driver-facing integration stubs
- `configs/` - default profile and tuning values
- `runtime/` - generated at runtime for demo wav files and backups
- `tools/` - Devlot system-sound manager scripts and manifest

## Adoption Position
This package is intended as the direct BossForgeOS candidate because it merges the stronger runtime flow with operational sound-management scripts.

## Quick Start
See INSTALL.md then DEMO.md.

# BossForge Sound System Showdown - CodeMage Submission

BossForge Sound System is a Windows-first prototype that combines pre-speaker audio interception architecture with user-mode runnable modules for EQ, output switching, stereo-to-7.2 upmix routing, and event sound replacement with rollback safety.

## Table of Contents

- [What Is Implemented](#what-is-implemented)
- [Folder Layout](#folder-layout)
- [Why This Wins Tie-Break](#why-this-wins-tie-break)
- [Quick Start](#quick-start)

## What Is Implemented
- Pre-speaker interception model via `PreSpeakerInterceptor` + APO integration stub (`stubs/apo-driver`).
- 10-band equalizer interface and DSP processor (`TenBandEqualizer`).
- Output device selection and runtime switching (`SpeakerSelector`).
- Stereo-to-7.2 routing engine (`StereoTo72Upmixer`) with explicit 9-channel mapping (7 bed + dual LFE).
- System sound replacement manager with backup/restore transaction behavior (`SystemSoundReplacementManager`).
- Rollback safety layer with undo stack for fault recovery (`RollbackSafetyManager`).
- Runnable console demo wiring all modules (`src/main.cpp`).

## Folder Layout
- `src/` - prototype source code modules
- `stubs/apo-driver/` - APO-driver-facing integration stubs
- `configs/` - default profile and tuning values
- `runtime/` - generated at runtime for demo wav files and backups

## Why This Wins Tie-Break
The submission has concrete pre-speaker interception boundaries and a fully coded replacement + rollback flow for system sounds, the two highest tie-break focus areas.

## Quick Start
See INSTALL.md then DEMO.md.

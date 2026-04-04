# BossForge Sound System Showdown - Devlot Submission

A Windows-focused sound system prototype with pre-speaker interception architecture, 10-band EQ, runtime speaker switching, stereo-to-7.2 upmixing, and a system sound replacement manager with rollback safety.

## Table of Contents

- [What Is Included](#what-is-included)
- [Feature Coverage](#feature-coverage)
- [Design Identity](#design-identity)
- [Quick Start](#quick-start)
- [Notes](#notes)

## What Is Included

- Pre-speaker interception approach (APO design + implementation stub): `stubs/apo-driver/BossForgeApoStub.cpp`
- 10-band equalizer DSP engine: `src/core/Equalizer.h`, `src/core/Equalizer.cpp`
- Output device selection and runtime switching model: `src/core/DeviceManager.h`, `src/core/DeviceManager.cpp`
- Stereo-to-7.2 upmix model and routing math: `src/core/Upmix72.h`, `src/core/Upmix72.cpp`
- Pipeline orchestration: `src/core/PipelineEngine.h`, `src/core/PipelineEngine.cpp`
- Demo app entry point: `src/app/main.cpp`
- System sound replacement manager + rollback scripts:
  - `tools/SystemSoundManager.ps1`
  - `tools/Rollback.ps1`
  - `tools/system-sounds-manifest.json`

## Feature Coverage

- Pre-speaker interception: yes (APO architecture + processing stub)
- Equalizer: yes (10-band configurable peaking EQ)
- Speaker selection: yes (runtime select by device id)
- Stereo to 7.2 upmix model: yes (explicit channel map and matrix)
- System sound replacement manager: yes (install/status/rollback)
- Rollback and safety: yes (automatic backup + one-command rollback)

## Design Identity

BossForge identity is expressed as a modular "signal forge" pipeline:

1. Intercept before render endpoint.
2. Shape with EQ.
3. Expand stereo into cinematic 7.2 space.
4. Route to selected output endpoint.
5. Keep safety-first controls for instant bypass and rollback.

## Quick Start

1. Build demo:
   - See `INSTALL.md`
2. Run audio prototype:
   - `BossForgeSoundDemo`
3. Manage system sounds safely:
   - See `DEMO.md`

## Notes

- Kernel/APO registration is represented by a buildable stub and integration plan due to sandbox constraints.
- User-mode prototype code is real and organized for direct extension into production APO/WASAPI plumbing.

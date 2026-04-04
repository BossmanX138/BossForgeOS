# BossForge Devlot Submission - Windows Sound System Showdown

BossForge Resonance Engine is a Windows-first audio control prototype that fuses user-mode runnable DSP with a privileged APO/driver integration blueprint.

## Table of Contents

- [What this submission delivers](#what-this-submission-delivers)
- [Submission structure](#submission-structure)
- [Quick start](#quick-start)
- [Safety first](#safety-first)

## What this submission delivers
- Pre-speaker interception approach:
  - Runnable now: user-mode loopback interception pipeline (WASAPI loopback -> DSP -> selected speaker endpoint).
  - Production path: endpoint APO/driver stubs and install plan for true endpoint integration.
- 10-band EQ in processing chain.
- Output device selection with runtime switch.
- Stereo upmix routing model up to 7.2.
- Windows system sound replacement manager with backup and restore safety.

## Submission structure
- `src/BossForge.SoundSystem`: runnable user-mode prototype.
- `stubs/apo-driver`: privileged integration stubs and install plan.
- `scripts`: PowerShell scripts for backup/apply/restore sound themes.
- `assets/system-sound-profile-template`: expected WAV naming for replacement profile packs.

## Quick start
See `INSTALL.md` and `DEMO.md`.

## Safety first
Always create a backup before replacing system sounds:
- App menu option `7` in the prototype.
- Or `scripts/backup-system-sounds.ps1`.

Rollback is documented in `INSTALL.md` and `stubs/apo-driver/INSTALL_APO.md`.

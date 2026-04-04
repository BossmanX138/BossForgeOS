# Architecture

## 1. Pre-Speaker Interception Approach

### Goal
Intercept PCM audio before final speaker endpoint output so DSP can be applied consistently across apps.

### Windows Path
- Primary production path: custom Windows Audio Processing Object (APO) registered as SFX/MFX at render endpoint pipeline.
- Prototype path in this submission:
  - APO processing behavior is represented in `stubs/apo-driver/BossForgeApoStub.cpp`.
  - User-mode DSP pipeline is implemented in `src/core/*`.

### Interception Stages
1. Render stream enters pre-speaker hook (APO `Process` equivalent).
2. Per-frame DSP (EQ + optional upmix fold behavior).
3. Endpoint render writes transformed samples.

## 2. DSP Core

### 10-Band EQ
- Class: `TenBandEqualizer`
- Bands: 31.25 Hz, 62.5 Hz, 125 Hz, 250 Hz, 500 Hz, 1 kHz, 2 kHz, 4 kHz, 8 kHz, 16 kHz
- Gain range: -18 dB to +18 dB
- Method: peaking biquad per band, cascaded processing for stereo frames

### Stereo-to-7.2 Upmix Model
- Class: `StereoTo72Upmixer`
- Channels:
  - Front Left, Front Right, Center
  - LFE1, LFE2
  - Side Left, Side Right
  - Rear Left, Rear Right
- Model:
  - Mid/side extraction from stereo
  - Center derived from mid
  - Side and rear spread from stereo + side energy
  - Dual LFEs from controlled low-energy feed

## 3. Device Selection and Routing

- Class: `DeviceManager`
- Responsibilities:
  - enumerate available output device objects
  - track current selected output endpoint id
  - support runtime switching via `selectDeviceById(...)`

In production, this maps to MMDevice endpoint IDs and dynamic graph rebinding.

## 4. Pipeline Orchestration

- Class: `PipelineEngine`
- Sequence:
  1. optional bypass check
  2. EQ process
  3. upmix to 7.2 frame
  4. route to active output device

## 5. System Sound Replacement Manager

- Script: `tools/SystemSoundManager.ps1`
- Registry root: `HKCU:\AppEvents\Schemes\Apps\.Default`
- Modes:
  - `install`: applies event sound mapping from manifest after backup
  - `status`: reports current mapped sounds
  - `rollback`: restores from selected or latest backup

## 6. Rollback and Safety

### Audio Runtime Safety
- Bypass mode in `PipelineEngine` for immediate DSP disable.
- Conservative upmix coefficients to avoid clipping spikes.

### System Sound Safety
- Pre-change backup is automatic on `install`.
- Backup files stored at `tools/backups/system-sounds-backup-*.json`.
- One-command restore: `tools/Rollback.ps1`.

## 7. Integration Plan (Production)

1. Build COM-based APO DLL implementing required interfaces (`IAudioProcessingObject`, configuration/property store interfaces).
2. Register APO with INF/registry under target endpoint effect chain.
3. Wire shared parameter block for real-time EQ band updates from UI.
4. Replace mock `DeviceManager` with MMDevice enumeration and notifications.
5. Add limiter stage and telemetry for clipping/latency protection.

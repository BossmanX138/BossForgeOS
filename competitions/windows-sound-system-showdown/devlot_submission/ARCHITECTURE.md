# Architecture

## 1. System Overview

This submission ships a two-lane architecture:

1. Runnable user-mode lane (implemented now)
- Captures mixed system audio using WASAPI loopback.
- Applies 10-band EQ.
- Applies stereo to 7.2 routing model.
- Folds down or maps to selected endpoint format.
- Renders to selected output device.

2. Privileged endpoint lane (stubbed with clear plan)
- Endpoint APO/driver route for true pre-speaker processing in Windows audio engine.
- COM/APO skeleton and installation command templates included.

## 2. Processing Graph (Runnable)

`Loopback Capture -> Buffered Provider -> Stereo Normalization -> 10-Band EQ -> Stereo-to-7.2 Upmix -> Channel Fold-Down -> Selected Output Device`

### Components
- `PreSpeakerInterceptor`
  - Owns capture and renderer lifecycle.
  - Rebuilds chain on runtime changes (EQ preset/device/layout).
- `TenBandEqualizerSampleProvider`
  - 10 peaking filters built from RBJ biquad equations.
- `StereoTo72UpmixerSampleProvider`
  - 9-channel virtual bus: `FL FR FC BL BR SL SR LFE1 LFE2`.
- `ChannelFoldDownSampleProvider`
  - Preserves expanded bus energy when output endpoint has fewer channels.
- `DeviceManager`
  - Enumerates render endpoints and resolves selected device.

## 3. System Sound Replacement

- `SystemSoundManager`
  - Reads/writes `HKCU\\AppEvents\\Schemes\\Apps\\.Default\\<event>\\.Current`.
  - Supports event profile application from WAV folder.
- `SafetyRollbackManager`
  - Creates local backup JSON snapshot.
  - Restores exact prior paths.

## 4. True Pre-Speaker Integration Path

`stubs/apo-driver` contains the privileged evolution path:

- `BossForgeApoStub.h/.cpp`
  - COM APO placeholder for endpoint processing callback.
- `INSTALL_APO.md`
  - Signing, registration, service restart, rollback commands.
- `routing-model.md`
  - Channel routing spec shared with user-mode prototype.

## 5. Safety and Recovery Design

- Every sound replacement flow begins with backup.
- Backup path is deterministic in `%LOCALAPPDATA%\\BossForgeSoundSystem`.
- Rollback is available through both app menu and scripts.
- APO lane includes explicit registry rollback commands.

## 6. Why this is feasible on Windows

- Uses established Windows audio stack interfaces (WASAPI in user-mode; APO in privileged path).
- Keeps user-mode prototype fully testable without requiring a custom driver install.
- Keeps production-grade endpoint insertion path explicit for post-sandbox hardening.

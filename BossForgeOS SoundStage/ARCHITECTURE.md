# ARCHITECTURE - BossForge Sound System

## 1. Pre-Speaker Interception Strategy

### Target Interception Point
The intended production interception point is an Audio Processing Object in the Windows shared-mode render path:
- Endpoint effect APO (LFX/GFX style insertion)
- Real-time hook analogous to `IAudioProcessingObjectRT::APOProcess`
- Position: after app mix, before final endpoint speaker render

### In-Race Implementation
Because kernel-signing + privileged install is out of sandbox scope, this submission implements:
- A concrete `PreSpeakerInterceptor` API and telemetry model
- A real hook registration pathway that processes buffers before upmix/output routing
- An APO integration stub (`BossForgeApoStub`) that captures identity, category, and format validation behavior

This yields a direct migration path from user-mode prototype to deployable APO package.

## 2. DSP Chain
1. Intercept stereo frame buffer
2. Apply 10-band EQ profile (gain clamped -12 dB to +12 dB)
3. Route through stereo-to-7.2 upmix matrix
4. Send to selected speaker endpoint device

## 3. Output Routing and Selection
- `SpeakerSelector` maintains discovered devices and active output endpoint.
- Runtime switching is instant and id-based.
- Console panel demonstrates live active-device changes.

## 4. Stereo-to-7.2 Upmix Model
`StereoTo72Upmixer` expands each stereo frame into:
- Front L/R
- Center (mono weighted)
- LFE1 and LFE2 (low-frequency weighted)
- Side L/R
- Rear L/R

Weighting decisions:
- Center emphasizes dialog from mono sum
- Side channels preserve spatial contrast using side signal
- Rear channels blend ambient tail from source and mono foundation

## 5. System Sound Replacement Manager
`SystemSoundReplacementManager` handles event sounds (`open_app`, `close_app`, notification-class extensible):
- Registers canonical event -> wav target
- Creates backups under `runtime/sound_backups`
- Performs replacement copy with transaction undo handler
- Restores defaults from backup set

## 6. Safety and Rollback
- `RollbackSafetyManager` supports transaction boundaries and reverse-order undo execution.
- Sound swap uses rollback on write failure.
- Restore-defaults path is always available and idempotent.

## 7. BossCrafts Design Language (Engineering Form)
- Aggressive low-latency intercept-first architecture
- Arena profile presets via `configs/default_profile.json`
- Explicit control surfaces: EQ, output target, upmix mode, safety toggle

## 8. Production Integration Plan
1. Convert APO stub into COM APO implementation with endpoint registration INF
2. Add signed installer and policy-safe activation flow
3. Bind UI shell (WinUI/WPF) to runtime control services
4. Move system-sound writes to privileged helper with UAC prompts + audit logs
5. Add automated integration tests for rollback and channel matrix correctness

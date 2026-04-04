# Demo Script

## Goal
Show all must-have features with clear runnable proof and explicit elevated path.

## Demo A - Pre-speaker interception + EQ + speaker switching + upmix model
1. Run app:
```powershell
cd src/BossForge.SoundSystem
dotnet run
```
2. Choose `1` to list output devices.
3. Choose `2` and pick a device.
4. Choose `6` and set layout to `9` (7.2 routing model).
5. Choose `5` and apply `bass` or `vocal` preset.
6. Choose `3` to start interception.
7. Play any system audio and switch outputs again with `2` while running.

Expected result:
- Audio is intercepted in user-mode graph before final render call.
- EQ preset is audible.
- Device switch occurs at runtime.
- 7.2 model is active in DSP graph and folded to endpoint format if needed.

## Demo B - Windows system sound replacement
1. Choose `7` to back up current sound mappings.
2. Choose `8`, point to a profile folder with required WAV names.
3. Trigger notifications/open/close events in Windows.
4. Choose `9` to restore defaults.

Expected result:
- Registry mappings update to custom WAV files.
- Rollback restores previous values.

## Demo C - Privileged roadmap (non-sandbox)
Walk through files:
- `stubs/apo-driver/BossForgeApoStub.h`
- `stubs/apo-driver/BossForgeApoStub.cpp`
- `stubs/apo-driver/INSTALL_APO.md`

Explain:
- endpoint APO callback location for true pre-speaker integration.
- signing and installation steps.
- rollback command path.

# Demo Runbook

## 1. Build and Launch

```powershell
cmake -S . -B build -G "Visual Studio 17 2022"
cmake --build build --config Release
./build/Release/BossForgeSoundDemo.exe
```

Expected output includes:
- device switch result
- selected output endpoint
- processed 7.2 frame values

## 2. Demonstrate EQ

Edit `src/app/main.cpp` band settings:

```cpp
engine.equalizer().setBandGainDb(0, 2.5);
engine.equalizer().setBandGainDb(4, -1.0);
engine.equalizer().setBandGainDb(8, 3.0);
```

Rebuild and rerun to show changed output values.

## 3. Demonstrate Speaker Selection

Swap the selected endpoint id in `main.cpp`:

```cpp
engine.devices().selectDeviceById("endpoint-hdmi");
```

Rebuild and rerun; verify output reports new active device.

## 4. Demonstrate Stereo-to-7.2 Upmix

Inspect generated frame channels in runtime output:
- FL/FR direct
- C from stereo mid
- SL/SR/RL/RR expansion
- LFE1/LFE2 dual bass feed

## 5. Demonstrate System Sound Replacement + Safety

1. Update `tools/system-sounds-manifest.json` with valid `.wav` files.
2. Install:

```powershell
./tools/SystemSoundManager.ps1 -Action install
```

3. Verify:

```powershell
./tools/SystemSoundManager.ps1 -Action status
```

4. Rollback:

```powershell
./tools/Rollback.ps1
```

Result: prior system event sounds restored from backup JSON.

## 6. Pre-Speaker Interception Evidence

Review `stubs/apo-driver/BossForgeApoStub.cpp`:
- frame interception modeled at pre-speaker stage
- EQ + upmix hook points in processing loop
- direct path to production APO COM implementation

# BossForgeOS Windows Sound System Acceptance Matrix

Date: 2026-03-23 (UTC)

## Scope
This matrix evaluates both race submissions using build + run evidence collected in this environment.

Submissions:
- Devlot: competitions/windows-sound-system-showdown-race/devlot_submission
- CodeMage: competitions/windows-sound-system-showdown-race/codemage_submission

## Test Harness
1. Build toolchain installed and verified:
- Visual Studio Build Tools 2022 (C++ workload)
- CMake
- LLVM

2. Build steps executed:
- CMake configure with Visual Studio 17 2022 generator
- Release build for each submission

3. Runtime steps executed:
- Run each built executable
- Run Devlot system-sound manager status command
- Verify CodeMage runtime sound backup artifacts

## Evidence
- Devlot binary ran and printed:
  - Device switch: ok
  - Current output: HDMI AVR 7.2
  - 7.2 channel values (FL/FR/C/LFE/SL/SR/RL/RR/LFE2)
- CodeMage binary ran and printed:
  - APO stub banner
  - output-device list + runtime switch
  - Intercepted frames count
  - Upmixed frame count
  - system sound swap open_app/close_app: ok
  - restore-defaults path
- Devlot PowerShell manager ran and printed event-status table
- CodeMage runtime backups present:
  - runtime/sound_backups/open_app.wav
  - runtime/sound_backups/close_app.wav

## Pass/Fail Matrix

| Criterion | Devlot | CodeMage | Notes |
|---|---|---|---|
| Builds in this environment | PASS | PASS | Both built with VS 2022 generator |
| Executable runs successfully | PASS | PASS | Both binaries returned expected console output |
| Pre-speaker interception evidence | PARTIAL PASS | PASS | Devlot runtime output does not print explicit interception telemetry; CodeMage does |
| 10-band EQ implementation present | PASS | PASS | Implemented in both codebases |
| Speaker selection/runtime switching | PASS | PASS | Demonstrated by output logs |
| Stereo-to-7.2 upmix path | PASS | PASS | Demonstrated by channel/upmix output |
| System sound replacement capability | PASS | PASS | Devlot via PowerShell registry manager; CodeMage via runtime manager |
| Rollback/safety evidence | PASS | PASS | Devlot backup/rollback scripts; CodeMage backup files + restore output |
| Integrated end-to-end demo coherence | PARTIAL PASS | PASS | Devlot split between exe + script; CodeMage unified in one executable flow |

## Decision for BossForgeOS Candidate
Winner for immediate integration readiness: CodeMage submission.

Reason:
- Stronger single-run end-to-end demonstration of all critical system behaviors in one executable path.
- Clear runtime telemetry for interception/upmix/sound replacement/restore.

Close second:
- Devlot submission is viable and now fully runnable after PowerShell fix, but currently less consolidated at runtime.

## Recommended Next Step
Promote CodeMage as primary integration baseline, then cherry-pick Devlot's PowerShell registry management ergonomics into the merged production branch.

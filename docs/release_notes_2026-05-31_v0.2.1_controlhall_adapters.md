# BossForgeOS v0.2.1 Control Hall Adapters (May 31, 2026)

## Highlights
- Added CI coverage for `module doctor --include-external`.
- Split AgentForge API route logic into `modules/agentforge/api_adapter.py`.
- Added Control Hall model route integration tests for adapter-backed endpoints.
- Added `module doctor` runbook for standard diagnostics.

## Adapter Progress
- SoundForge routes use `modules/soundforge/api_adapter.py`.
- Model Gateway routes use `modules/model_gateway/api_adapter.py`.
- AgentForge profile/icon routes now use `modules/agentforge/api_adapter.py`.

## Verification
- Unit tests pass locally.
- `bforge module doctor --include-external` passes with all module smokes green.

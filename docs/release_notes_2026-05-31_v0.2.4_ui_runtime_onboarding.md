# BossForgeOS v0.2.4 UI Runtime + Onboarding Adapters (May 31, 2026)

## Highlights
- Extracted pin-overlay route logic into `modules/ui_runtime/api_adapter.py`.
- Extracted onboarding step/status logic into `modules/onboarding/api_adapter.py`.
- Added Control Hall route-contract tests for pin and onboarding endpoints.

## Adapter Progress
- SoundForge adapter: complete
- Model Gateway adapter: complete
- AgentForge adapter: complete
- Security adapter: complete
- IconForge adapter: complete
- UI Runtime (pin overlay) adapter: complete
- Onboarding adapter: complete

## Validation
- Unit tests pass with new route-contract suites.
- `bforge module doctor --include-external --json` remains healthy.

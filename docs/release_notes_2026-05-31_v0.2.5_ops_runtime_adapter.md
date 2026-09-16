# BossForgeOS v0.2.5 Ops Runtime Adapter (May 31, 2026)

## Highlights
- Extracted scheduler and CI/CD route logic into `modules/ops_runtime/api_adapter.py`.
- Added route-contract tests for `/api/scheduler` and `/api/cicd`.
- Added safe command-policy tests for scheduler command validation.

## Adapter Progress
- SoundForge: complete
- Model Gateway: complete
- AgentForge: complete
- Security: complete
- IconForge: complete
- UI Runtime (pin): complete
- Onboarding: complete
- Ops Runtime (scheduler + cicd): complete

## Validation
- Unit test suite passes with new ops and command-policy coverage.
- `bforge module doctor --include-external --json` remains healthy.

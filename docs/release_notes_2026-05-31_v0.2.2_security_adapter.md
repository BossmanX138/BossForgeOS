# BossForgeOS v0.2.2 Security Adapter (May 31, 2026)

## Highlights
- Extracted Security API route logic into `modules/security/api_adapter.py`.
- Added `bforge module doctor --json` for machine-parsed diagnostics.
- Added Control Hall security route contract tests.
- Added `scripts/bootstrap_dev_env.ps1` for repeatable Conda + dependency + shim setup.
- CI now runs `module doctor --include-external`.

## Adapter Progress
- SoundForge adapter: complete.
- Model Gateway adapter: complete.
- AgentForge adapter: complete.
- Security adapter: complete.

## Validation
- Unit test suite passes.
- `bforge module doctor --include-external --json` returns compact JSON and passes checks.

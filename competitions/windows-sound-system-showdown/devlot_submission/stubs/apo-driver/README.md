# APO and Driver Stub Package

This folder defines the privileged extension path for true pre-speaker interception at the Windows audio engine endpoint.

## Table of Contents

- [Why this exists](#why-this-exists)
- [Included stubs](#included-stubs)
- [Security and rollback](#security-and-rollback)

## Why this exists
User-mode loopback interception is runnable now, but a production-grade pre-speaker chain requires one of these privileged mechanisms:

1. System Effects APO (SFX/MFX/EFX) for endpoint processing.
2. Virtual audio endpoint driver plus user-mode processing service.

## Included stubs
- `BossForgeApoStub.h`: COM/APO interface skeleton.
- `BossForgeApoStub.cpp`: processing and registration placeholders.
- `INSTALL_APO.md`: signing, registration, and rollback commands.
- `routing-model.md`: channel map for stereo to 7.2 translation.

## Security and rollback
- Deploy only on test-signed systems first.
- Keep a restore point and exported relevant registry keys before APO registration.
- Use `INSTALL_APO.md` rollback section to revert instantly.

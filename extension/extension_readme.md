# Extension README

Canonical subsystem readme for `extension`.

## Purpose

Houses the VS Code extension and Electron shell surfaces for BossForgeOS.

## Current State

- Contains the extension workspace integration surface and Electron shell compatibility layer.
- Canonical extension behavior should be tracked in this file to avoid drift between legacy startup docs and active workflows.

## Canonical References

- `extension/README.md`
- `extension/electron-shell/README.md`

## Growth Opportunities

- Document extension-to-Control Hall contract boundaries and failure fallback behavior.
- Maintain a command-to-handler map for registered extension commands.

## TODO

- Add a `Contracts` section for command routing, bus writes, and Control Hall API dependencies.
- Add a `Command Inventory` table tied to extension command registrations.

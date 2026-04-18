# BossCrafts VS Code Extension

This extension is an active BossForgeOS editor integration surface.

## Table of Contents

- [Commands](#commands)
- [Behavior](#behavior)
- [Next Steps](#next-steps)

## Commands

- BossCrafts: Show Status
- BossCrafts: Send Selection To CodeMage
- BossCrafts: Open Control Hall

## Behavior

- Writes command files into the BossCrafts Rune Bus command directory.
- Uses `BOSSFORGE_ROOT` if set, else defaults to `%USERPROFILE%/BossCrafts`.

## Current State

- Supports command palette interactions for status, selection dispatch, and Control Hall opening.
- Acts as an adapter between editor workflows and runtime command transport.

## Next Steps

- Add event stream view and response panel.
- Add extension sidebar webview.
- Add endpoint and ritual command actions.
- Add packaging workflow (`vsce`).

## TODO

- Reconcile this command list with registered extension commands and prune stale entries.
- Add extension-to-Control Hall dependency notes and fallback behavior.

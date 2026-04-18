# Launcher README

Canonical subsystem readme for `launcher`.

## Purpose

Owns process bootstrap, daemon startup orchestration, and Control Hall launch wiring.

## Current State

- Primary entrypoint is `python -m launcher.bossforge_launcher`.
- Supports runtime modes including hall-only and daemon-only execution paths, host/port control, and internal model routing setup.

## Growth Opportunities

- Maintain an authoritative launcher flag table sourced from argparse definitions.
- Introduce named startup profiles (dev, safe-mode, headless automation).

## TODO

- Add a `Current Flags Snapshot` section with defaults and failure-mode notes.
- Add startup profiles and map each profile to expected services.

# UI README

Canonical subsystem readme for `ui`.

## Purpose

Hosts Control Hall UI server and front-end assets.

## Current State

- Control Hall is served via `ui/control_hall.py` and includes runtime panel endpoints and integration with launcher-managed services.
- UI behavior is coupled to backend API and daemon contract changes.
- Theme tokens are now published for reuse in `assets/ui/bossforge_theme_tokens.json` and `assets/ui/bossforge_theme.css`.

## Growth Opportunities

- Publish a panel ownership map (panel -> owning subsystem).
- Add endpoint-to-panel mapping for safer UI/API evolution.

## TODO

- Add a `Panel and Endpoint Contract` section with owning modules.
- Document release cadence expectations for UI-impacting backend changes.

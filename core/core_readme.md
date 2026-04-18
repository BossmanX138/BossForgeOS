# Core README

Canonical subsystem readme for `core`.

## Purpose

Core is the runtime authority for agent orchestration, daemon lifecycle, connectors, security controls, schema contracts, model routing, and bus integration.

## Current State

- Runtime implementations are organized by role-specific subfolders (`agents`, `daemons`, `connectors`, `security`, `schemas`, `voice`, `model`).
- New runtime behavior lands in `core` first; outer layers should remain adapters.

## Growth Opportunities

- Publish a subfolder ownership and stability map to reduce boundary drift.
- Document cross-subsystem contracts for core-to-ui and core-to-extension interactions.

## TODO

- Add a `Subfolder Ownership Matrix` with owner, stability level, and review cadence.
- Add a `Contract Surfaces` section listing key API/event boundaries.

# 365 Integration README

Canonical subsystem readme for `365 Integration`.

## Purpose

Contains Microsoft 365 integration assets and related automation hooks.

## Current State

- Keep integration contracts explicit and documented.
- Store tenant-specific secrets/config outside source control.

This directory should focus on cross-cutting integration strategy while connector-specific runtime logic remains in connector folders.

## Growth Opportunities

- Define clearer boundary between integration strategy docs and executable connector implementation.

## TODO

- Add boundary section with examples of what belongs here versus connector subsystems.
